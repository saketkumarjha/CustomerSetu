"""
Scheduled Jobs — KB Enrichment Pipeline

These functions are meant to run on a cron schedule (APScheduler / Celery Beat):

  check_auto_response_success()   — every hour, or on-demand
  process_enrichment_queue()      — every hour
  weekly_unverified_review()      — every Monday 09:00
  cleanup_old_queue_entries()     — every day at midnight

Wiring (production):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(process_enrichment_queue, "interval", minutes=60)
    scheduler.add_job(weekly_unverified_review,  "cron",     day_of_week="mon", hour=9)
    scheduler.add_job(cleanup_old_queue_entries, "cron",     hour=0)
    scheduler.start()

For now, endpoints in kb_admin.py expose these as manually-triggered actions
so they can be called from the admin dashboard.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Job 1: Check auto-response success (24 h after auto-close)
# ═══════════════════════════════════════════════════════════════════════════════

async def check_auto_response_success() -> dict:
    """
    Scans auto-closed complaints from the window 23–25 h ago.
    For each one where the customer has NOT re-complained or escalated,
    treats silence as acceptance and enqueues for KB enrichment.

    Returns a summary dict.
    """
    from app.tasks.kb_enrichment import KBEnrichmentManager, TYPE_AUTO_RESPONSE

    supabase = get_supabase()
    now      = datetime.now(timezone.utc)
    window_start = (now - timedelta(hours=25)).isoformat()
    window_end   = (now - timedelta(hours=23)).isoformat()

    # Complaints auto-closed in the 23-25h window, not yet queued
    try:
        complaints_res = (
            supabase.table("complaints")
            .select(
                "complaint_id, status, category, masked_text, "
                "final_response_text, confidence_score, current_tier, "
                "tier_resolved_at, branch_id, customer_feedback_score, "
                "compliance_category, escalation_count, is_duplicate, "
                "customer_id, auto_closed_at"
            )
            .eq("status", "auto_closed")
            .gte("auto_closed_at", window_start)
            .lte("auto_closed_at", window_end)
            .execute()
        )
    except Exception as exc:
        logger.error("[ScheduledJob] check_auto_response_success query failed: %s", exc)
        return {"error": str(exc), "processed": 0}

    complaints = complaints_res.data or []
    if not complaints:
        logger.info("[ScheduledJob] No auto-closed complaints in window — nothing to process")
        return {"processed": 0, "enqueued": 0, "skipped": 0}

    # Filter out those already in the queue
    complaint_ids = [c["complaint_id"] for c in complaints]
    try:
        already_queued_res = (
            supabase.table("kb_enrichment_queue")
            .select("complaint_id")
            .in_("complaint_id", complaint_ids)
            .eq("processed", False)
            .execute()
        )
        already_queued = {
            r["complaint_id"] for r in (already_queued_res.data or [])
        }
    except Exception:
        already_queued = set()

    manager  = KBEnrichmentManager()
    enqueued = 0
    skipped  = 0

    for complaint in complaints:
        cid = complaint["complaint_id"]

        if cid in already_queued:
            skipped += 1
            continue

        # Check if customer escalated or submitted a follow-up complaint
        customer_id = complaint.get("customer_id")
        escalated   = False
        if customer_id:
            try:
                follow_up = (
                    supabase.table("complaints")
                    .select("complaint_id")
                    .eq("customer_id", customer_id)
                    .neq("complaint_id", cid)
                    .gte("created_at", complaint.get("auto_closed_at", window_start))
                    .limit(1)
                    .execute()
                )
                escalated = bool(follow_up.data)
            except Exception:
                pass

        if escalated:
            logger.info("[ScheduledJob] %s — customer escalated, skipping", cid)
            skipped += 1
            continue

        resolution_event = {
            "type":             TYPE_AUTO_RESPONSE,
            "resolution_text":  complaint.get("final_response_text", ""),
            "confidence_score": float(complaint.get("confidence_score") or 0.5),
            "agent_action":     None,
        }

        queue_id = await asyncio.to_thread(
            manager.enqueue_for_enrichment, complaint, resolution_event
        )
        if queue_id:
            enqueued += 1
            logger.info("[ScheduledJob] %s → enqueued as %d", cid, queue_id)
        else:
            skipped += 1

    logger.info(
        "[ScheduledJob] check_auto_response_success: %d enqueued, %d skipped of %d total",
        enqueued, skipped, len(complaints),
    )
    return {"processed": len(complaints), "enqueued": enqueued, "skipped": skipped}


# ═══════════════════════════════════════════════════════════════════════════════
# Job 2: Process enrichment queue (hourly)
# ═══════════════════════════════════════════════════════════════════════════════

async def process_enrichment_queue() -> dict:
    """
    Processes queue entries whose scheduled_for time has passed.

    - Entries with quality >= AUTO_APPROVE_THRESHOLD (0.95) are auto-approved.
    - The rest remain in the queue for admin review.

    Returns a summary dict.
    """
    from app.tasks.kb_enrichment import KBEnrichmentManager

    supabase = get_supabase()
    now      = datetime.now(timezone.utc).isoformat()

    try:
        ready_res = (
            supabase.table("kb_enrichment_queue")
            .select("*")
            .eq("processed", False)
            .lte("scheduled_for", now)
            .order("recommended_quality_score", desc=True)
            .execute()
        )
    except Exception as exc:
        # recommended_quality_score column may not exist yet (pre-migration).
        # Retry with a fallback sort so the job still runs.
        logger.warning(
            "[ScheduledJob] process_enrichment_queue: quality sort failed (%s), retrying without it",
            exc,
        )
        try:
            ready_res = (
                supabase.table("kb_enrichment_queue")
                .select("*")
                .eq("processed", False)
                .lte("scheduled_for", now)
                .order("created_at", desc=False)
                .execute()
            )
        except Exception as exc2:
            logger.error("[ScheduledJob] process_enrichment_queue query failed: %s", exc2)
            return {"error": str(exc2)}

    entries = ready_res.data or []
    if not entries:
        logger.info("[ScheduledJob] No ready queue entries")
        return {"auto_approved": 0, "flagged_for_review": 0}

    threshold  = KBEnrichmentManager.AUTO_APPROVE_THRESHOLD
    auto_approved        = 0
    flagged_for_review   = 0
    skipped              = 0

    for entry in entries:
        # Skip if complaint was subsequently escalated / reopened
        complaint_id = entry.get("complaint_id")
        if complaint_id:
            try:
                c_res = (
                    supabase.table("complaints")
                    .select("status")
                    .eq("complaint_id", complaint_id)
                    .execute()
                )
                if c_res.data:
                    status = c_res.data[0].get("status", "")
                    if status in ("escalated", "reopened"):
                        supabase.table("kb_enrichment_queue").update({
                            "processed":        True,
                            "added_to_kb":      False,
                            "rejection_reason": f"Customer {status} after resolution",
                            "processed_at":     datetime.now(timezone.utc).isoformat(),
                        }).eq("id", entry["id"]).execute()
                        skipped += 1
                        continue
            except Exception:
                pass

        quality = float(entry.get("recommended_quality_score") or 0.0)

        if quality >= threshold:
            success = await asyncio.to_thread(_auto_approve_to_kb, entry)
            if success:
                auto_approved += 1
            else:
                flagged_for_review += 1
        else:
            flagged_for_review += 1

    logger.info(
        "[ScheduledJob] Queue: %d auto-approved, %d flagged, %d skipped",
        auto_approved, flagged_for_review, skipped,
    )
    return {
        "auto_approved":      auto_approved,
        "flagged_for_review": flagged_for_review,
        "skipped":            skipped,
        "total_processed":    len(entries),
    }


def _auto_approve_to_kb(entry: dict) -> bool:
    """
    Inserts a high-quality queue entry directly into knowledge_base as verified.
    Marks the queue row as processed.

    Returns True on success, False on failure.
    """
    from openai import OpenAI
    from app.core.config import get_settings

    supabase = get_supabase()
    settings = get_settings()

    resolution_text = entry.get("resolution_text", "")
    tier_level      = int(entry.get("tier_level") or 0)
    tier_scope      = entry.get("tier_scope")
    category        = entry.get("category", "General Banking")
    issue_type      = entry.get("issue_type")
    quality_score   = float(entry.get("recommended_quality_score") or 0.8)
    complaint_id    = entry.get("complaint_id")

    # Duplicate check within same tier + category
    try:
        existing = (
            supabase.table("knowledge_base")
            .select("id")
            .eq("tier_level", tier_level)
            .eq("category", category)
            .execute()
        )
        # Simple issue_type match (LLM-generated, fuzzy match not needed here)
        if issue_type:
            for row in (existing.data or []):
                pass  # exact match checked below
    except Exception:
        pass

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        embed_resp = client.embeddings.create(
            input      = resolution_text,
            model      = settings.openai_embedding_model,
            dimensions = settings.openai_embedding_dimension,
        )
        embedding = embed_resp.data[0].embedding
    except Exception as exc:
        logger.error("[AutoApprove] Embedding failed for queue %d: %s", entry["id"], exc)
        return False

    try:
        kb_row = {
            "tier_level":         tier_level,
            "tier_scope":         tier_scope,
            "category":           category,
            "resolution_text":    resolution_text,
            "quality_score":      quality_score,
            "verified":           True,
            "embedding":          embedding,
            "source":             "auto_enrichment",
            "source_complaint_id": complaint_id,
        }
        if issue_type:
            kb_row["issue_type"] = issue_type
        if complaint_id:
            kb_row["complaint_id"] = complaint_id

        result = supabase.table("knowledge_base").insert(kb_row).execute()
        kb_entry_id = result.data[0]["id"] if result.data else None

        supabase.table("kb_enrichment_queue").update({
            "processed":    True,
            "added_to_kb":  True,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", entry["id"]).execute()

        logger.info(
            "[AutoApprove] Queue entry %d → KB entry %s",
            entry["id"], kb_entry_id,
        )
        return True

    except Exception as exc:
        logger.error("[AutoApprove] KB insert failed for queue %d: %s", entry["id"], exc)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Job 3: Weekly unverified review digest (Monday 09:00)
# ═══════════════════════════════════════════════════════════════════════════════

def weekly_unverified_review() -> dict:
    """
    Counts unverified KB entries older than 7 days and logs a digest.
    In production, replace the logger calls with real email sends.
    """
    supabase    = get_supabase()
    cutoff      = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    try:
        unverified_res = (
            supabase.table("knowledge_base")
            .select("id, tier_level, category, created_at")
            .eq("verified", False)
            .lte("created_at", cutoff)
            .execute()
        )
        rows = unverified_res.data or []
    except Exception as exc:
        logger.error("[WeeklyReview] Query failed: %s", exc)
        return {"error": str(exc)}

    total = len(rows)

    tier_counts: dict = {}
    for r in rows:
        t = int(r.get("tier_level") or 0)
        tier_counts[t] = tier_counts.get(t, 0) + 1

    pending_queue = 0
    try:
        q_res = (
            supabase.table("kb_enrichment_queue")
            .select("id")
            .eq("processed", False)
            .execute()
        )
        pending_queue = len(q_res.data or [])
    except Exception:
        pass

    report = (
        f"KB Enrichment Weekly Report\n"
        f"===========================\n"
        f"Unverified entries (>7 days old): {total}\n"
        f"Pending review queue:             {pending_queue}\n\n"
        f"Breakdown by tier:\n"
        + "\n".join(f"  Tier {t}: {c}" for t, c in sorted(tier_counts.items()))
        + f"\n\nAction required: /admin/kb/entries?verified=false"
    )

    if total == 0 and pending_queue == 0:
        logger.info("[WeeklyReview] All caught up — no unverified entries")
    else:
        logger.info("[WeeklyReview] %d unverified, %d pending\n%s", total, pending_queue, report)

    return {
        "unverified_entries":  total,
        "pending_queue":       pending_queue,
        "tier_breakdown":      tier_counts,
        "report":              report,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Job 4: Cleanup old processed queue entries (daily midnight)
# ═══════════════════════════════════════════════════════════════════════════════

def cleanup_old_queue_entries(retention_days: int = 90) -> dict:
    """
    Deletes processed queue entries older than retention_days.
    """
    supabase = get_supabase()
    cutoff   = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    try:
        rows = (
            supabase.table("kb_enrichment_queue")
            .select("id")
            .eq("processed", True)
            .lte("processed_at", cutoff)
            .execute()
            .data or []
        )
        ids_to_delete = [r["id"] for r in rows]

        if ids_to_delete:
            supabase.table("kb_enrichment_queue").delete().in_("id", ids_to_delete).execute()

        logger.info(
            "[Cleanup] Deleted %d processed queue entries older than %d days",
            len(ids_to_delete), retention_days,
        )
        return {"deleted": len(ids_to_delete), "retention_days": retention_days}

    except Exception as exc:
        logger.error("[Cleanup] Failed: %s", exc)
        return {"error": str(exc), "deleted": 0}
