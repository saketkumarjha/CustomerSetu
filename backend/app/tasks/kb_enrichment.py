"""
Knowledge Base Enrichment — Background Task + Enrichment Manager

Two entry points:
1. schedule_kb_enrichment()  — called from graph.py after auto-response (Route 1).
   Waits 24 h, then checks customer acceptance before adding to KB.

2. KBEnrichmentManager.enqueue_for_enrichment()  — called by ResolutionEventHandler
   for all routes (auto, human-accepted, human-edited).  Computes quality signals and
   writes a richer row to kb_enrichment_queue for admin / scheduled-job review.

Production note:
    Replace asyncio.sleep-based delay with Celery + Redis for distributed,
    persistent scheduling.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

_DEFAULT_DELAY_HOURS = 24

# ── Resolution event type constants ──────────────────────────────────────────
TYPE_AUTO_RESPONSE   = "AUTO_RESPONSE"
TYPE_AGENT_ACCEPTED  = "AGENT_ACCEPTED"
TYPE_AGENT_EDITED    = "AGENT_EDITED"

# ── Exclusion sets ────────────────────────────────────────────────────────────
_EXCLUDE_RBI_CATEGORIES = {"FRAUD", "LEGAL_DISPUTE"}
_EXCLUDE_AGENT_CATEGORIES = {"Fraud", "Legal Dispute"}


# ═══════════════════════════════════════════════════════════════════════════════
# KBEnrichmentManager
# ═══════════════════════════════════════════════════════════════════════════════

class KBEnrichmentManager:
    """
    Decides whether a resolved complaint should enter the KB enrichment queue,
    calculates a multi-signal quality score, and writes the queue row.
    """

    # Quality thresholds
    AUTO_APPROVE_THRESHOLD = 0.95
    REVIEW_THRESHOLD       = 0.70
    MIN_RESOLUTION_LENGTH  = 50
    MAX_RESOLUTION_LENGTH  = 5000
    MAX_ESCALATIONS        = 3

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue_for_enrichment(
        self,
        complaint: dict,
        resolution_event: dict,
    ) -> Optional[int]:
        """
        Main entry point.  Evaluates the resolution, computes quality signals,
        and inserts a row into kb_enrichment_queue.

        Returns the queue row id, or None if the entry was rejected.
        """
        should_add, payload = self.should_enqueue_for_enrichment(complaint, resolution_event)

        if not should_add:
            logger.info(
                "[KB] Skipping enrichment for %s: %s",
                complaint.get("complaint_id"), payload,
            )
            return None

        quality_signals = payload
        complaint_id = complaint.get("complaint_id", "")

        tier_level = int(
            complaint.get("tier_resolved_at") or complaint.get("current_tier") or 1
        )
        tier_scope = self.determine_tier_scope(complaint)
        category   = complaint.get("category", "General Banking")

        resolution_text = (
            resolution_event.get("edited_response")
            if resolution_event.get("type") == TYPE_AGENT_EDITED
            else resolution_event.get("resolution_text", "")
        )

        issue_type = self.generate_issue_type(complaint, resolution_text)
        scheduled_for = (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).isoformat()

        supabase = get_supabase()
        try:
            result = supabase.table("kb_enrichment_queue").insert({
                "complaint_id":             complaint_id,
                "tier_level":               tier_level,
                "tier_scope":               tier_scope,
                "category":                 category,
                "issue_type":               issue_type,
                "resolution_text":          resolution_text,
                "confidence_score":         float(resolution_event.get("confidence_score") or 0.0),
                "recommended_quality_score": quality_signals["score"],
                "quality_signals_json":     quality_signals,
                "agent_action":             resolution_event.get("agent_action"),
                "customer_feedback_score":  complaint.get("customer_feedback_score"),
                "resolution_type":          resolution_event.get("type", TYPE_AUTO_RESPONSE),
                "scheduled_for":            scheduled_for,
                "processed":                False,
                "added_to_kb":              False,
            }).execute()

            if result.data:
                queue_id = result.data[0]["id"]
                logger.info(
                    "[KB] Enqueued %s for enrichment (Queue ID: %d, Q: %.2f)",
                    complaint_id, queue_id, quality_signals["score"],
                )
                return queue_id

        except Exception as exc:
            logger.warning("[KB] Failed to enqueue %s: %s", complaint_id, exc)

        return None

    def should_enqueue_for_enrichment(
        self,
        complaint: dict,
        resolution_event: dict,
    ) -> tuple:
        """
        Returns (True, quality_signals_dict) or (False, reason_string).
        """
        # ── Exclusion checks ──────────────────────────────────────────────────
        if complaint.get("is_duplicate"):
            return False, "Duplicate complaint"

        escalation_count = int(complaint.get("escalation_count") or 0)
        if escalation_count > self.MAX_ESCALATIONS:
            return False, f"Too many escalations ({escalation_count})"

        rbi_cat = complaint.get("compliance_category", "")
        if rbi_cat in _EXCLUDE_RBI_CATEGORIES:
            return False, f"Sensitive RBI category: {rbi_cat}"

        cat = complaint.get("category", "")
        if cat in _EXCLUDE_AGENT_CATEGORIES:
            return False, f"Excluded category: {cat}"

        resolution_text = (
            resolution_event.get("edited_response")
            if resolution_event.get("type") == TYPE_AGENT_EDITED
            else resolution_event.get("resolution_text", "")
        ) or ""

        if len(resolution_text) < self.MIN_RESOLUTION_LENGTH:
            return False, f"Resolution too short ({len(resolution_text)} chars)"

        if len(resolution_text) > self.MAX_RESOLUTION_LENGTH:
            return False, "Resolution text exceeds maximum length"

        # ── Quality check ─────────────────────────────────────────────────────
        quality = self.calculate_quality_signals(complaint, resolution_event)

        # Human-reviewed resolutions are always worth queuing for admin inspection
        # regardless of the computed score — the agent's edit IS the quality signal.
        event_type = resolution_event.get("type", TYPE_AUTO_RESPONSE)
        if event_type in (TYPE_AGENT_ACCEPTED, TYPE_AGENT_EDITED):
            return True, quality

        if quality["score"] >= self.REVIEW_THRESHOLD:
            return True, quality
        return False, f"Quality score too low: {quality['score']:.2f}"

    def calculate_quality_signals(
        self,
        complaint: dict,
        resolution_event: dict,
    ) -> dict:
        """
        Computes a weighted quality score from multiple signals.

        Base weights (normalized when a signal is absent):
          AI confidence          0.30 (auto) / 0.15 (agent-edited, human text dominates)
          Agent validation       0.20 (accepted) / 0.40 (edited — human wrote the response)
          Customer satisfaction  0.25
          Tier generalisability  0.15
          First-time resolution  0.10

        Combined = sum(signal_value * weight) / sum(applicable_weights)
        This normalizes correctly when optional signals (CSAT) are absent.
        """
        signals: dict = {}
        # contributions[key] = (value, weight)
        contributions: dict = {}
        event_type = resolution_event.get("type", TYPE_AUTO_RESPONSE)
        conf = float(resolution_event.get("confidence_score") or 0.5)

        if event_type == TYPE_AUTO_RESPONSE:
            signals["ai_confidence"] = conf
            contributions["ai_confidence"] = (conf, 0.30)

        elif event_type == TYPE_AGENT_ACCEPTED:
            signals["ai_confidence"]    = conf
            signals["agent_validation"] = 1.0
            contributions["ai_confidence"]    = (conf, 0.30)
            contributions["agent_validation"] = (1.0,  0.20)

        elif event_type == TYPE_AGENT_EDITED:
            # Agent wrote a better response — human text is the dominant quality signal.
            signals["ai_confidence"]    = conf
            signals["agent_validation"] = 1.0
            contributions["ai_confidence"]    = (conf, 0.15)
            contributions["agent_validation"] = (1.0,  0.40)

        # Customer satisfaction (CSAT 1–5)
        csat = complaint.get("customer_feedback_score")
        if csat is not None:
            csat_norm = float(csat) / 5.0
            signals["customer_satisfaction"] = csat_norm
            contributions["customer_satisfaction"] = (csat_norm, 0.25)

        # Tier generalisability: lower tier = more broadly applicable
        tier_resolved = int(
            complaint.get("tier_resolved_at") or complaint.get("current_tier") or 1
        )
        tier_score = max(0.0, (6 - tier_resolved) / 6.0)
        signals["tier_generalizability"] = tier_score
        contributions["tier_generalizability"] = (tier_score, 0.15)

        # First-time resolution bonus
        escalation_count = int(complaint.get("escalation_count") or 0)
        ftr_score = 1.0 if escalation_count == 0 else 0.5
        signals["first_time_resolution"] = ftr_score
        contributions["first_time_resolution"] = (ftr_score, 0.10)

        # Normalized weighted average — dividing by sum of applicable weights, NOT len(scores)
        total_weight = sum(w for _, w in contributions.values())
        combined = (
            sum(v * w for v, w in contributions.values()) / total_weight
            if total_weight > 0 else 0.0
        )

        recommendation = (
            "approve" if combined >= 0.85
            else "review" if combined >= 0.70
            else "reject"
        )

        return {
            "signals":        signals,
            "score":          round(combined, 4),
            "recommendation": recommendation,
        }

    def determine_tier_scope(self, complaint: dict) -> Optional[str]:
        """
        Derives the KB tier_scope string from the complaint's tier and branch.

        Falls back to None gracefully if branch/zone/region tables are absent.
        """
        tier_level = int(
            complaint.get("tier_resolved_at") or complaint.get("current_tier") or 1
        )
        branch_id = complaint.get("branch_id")

        if tier_level == 0:
            return None

        if tier_level == 4:
            return "HEAD_OFFICE"

        if tier_level == 5:
            return "OMBUDSMAN"

        if not branch_id:
            return None

        supabase = get_supabase()

        try:
            if tier_level == 1:
                res = supabase.table("branches").select("code").eq("id", branch_id).execute()
                if res.data:
                    return f"BRANCH:{res.data[0]['code']}"

            elif tier_level == 2:
                br = supabase.table("branches").select("zone_id").eq("id", branch_id).execute()
                if br.data and br.data[0].get("zone_id"):
                    zn = supabase.table("zones").select("name").eq("id", br.data[0]["zone_id"]).execute()
                    if zn.data:
                        return f"ZONE:{zn.data[0]['name']}"

            elif tier_level == 3:
                br = supabase.table("branches").select("zone_id").eq("id", branch_id).execute()
                if br.data and br.data[0].get("zone_id"):
                    zn = supabase.table("zones").select("region_id").eq("id", br.data[0]["zone_id"]).execute()
                    if zn.data and zn.data[0].get("region_id"):
                        rg = supabase.table("regions").select("name").eq("id", zn.data[0]["region_id"]).execute()
                        if rg.data:
                            return f"REGION:{rg.data[0]['name']}"

        except Exception as exc:
            logger.debug("[KB] tier_scope lookup failed (tier %d): %s", tier_level, exc)

        return None

    def generate_issue_type(self, complaint: dict, resolution_text: str) -> str:
        """
        Uses GPT-4o-mini to extract a concise 5-10 word issue type.
        Falls back to 'category – complaint snippet' if the LLM call fails.
        """
        category    = complaint.get("category", "General Banking")
        masked_text = (complaint.get("masked_text") or "")[:300]

        try:
            from openai import OpenAI
            from app.core.config import get_settings

            settings = get_settings()
            client   = OpenAI(api_key=settings.openai_api_key)

            prompt = (
                "Extract a concise issue type (5-10 words) from this bank complaint.\n\n"
                f"Complaint: {masked_text}\n"
                f"Resolution: {resolution_text[:300]}\n"
                f"Category: {category}\n\n"
                "Return ONLY the issue type phrase, no explanation or punctuation."
            )

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0,
            )
            issue_type = resp.choices[0].message.content.strip().strip('"').strip("'")
            if issue_type and len(issue_type) <= 100:
                return issue_type

        except Exception as exc:
            logger.debug("[KB] generate_issue_type LLM call failed: %s", exc)

        short_text = masked_text[:50].rstrip(" .,") or "Complaint"
        return f"{category} - {short_text}"


# ── Module-level singleton ────────────────────────────────────────────────────

_manager = KBEnrichmentManager()


# ═══════════════════════════════════════════════════════════════════════════════
# Backward-compatible public entry point (called from graph.py — Route 1)
# ═══════════════════════════════════════════════════════════════════════════════

async def schedule_kb_enrichment(
    complaint_id: str,
    draft_response: str,
    confidence_score: float,
    tier_level: int,
    delay_hours: int = _DEFAULT_DELAY_HOURS,
) -> None:
    """
    Called immediately after an auto-response is sent (Route 1).

    Logs intent to kb_enrichment_queue, then schedules a 24-hour check.
    If the complaint is still auto_closed after 24 h (no customer escalation),
    the resolution is added to the knowledge base.
    """
    await _log_to_queue(complaint_id, draft_response, delay_hours)

    asyncio.create_task(
        _run_after_delay(
            complaint_id     = complaint_id,
            draft_response   = draft_response,
            confidence_score = confidence_score,
            tier_level       = tier_level,
            delay_seconds    = delay_hours * 3600,
        )
    )
    logger.info("[KB] Enrichment scheduled for %s in %d h", complaint_id, delay_hours)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _run_after_delay(
    complaint_id: str,
    draft_response: str,
    confidence_score: float,
    tier_level: int,
    delay_seconds: int,
) -> None:
    await asyncio.sleep(delay_seconds)
    await _process_enrichment(complaint_id, draft_response, confidence_score, tier_level)


async def _process_enrichment(
    complaint_id: str,
    draft_response: str,
    confidence_score: float,
    tier_level: int,
) -> None:
    """
    Runs after the 24-hour delay.
    Fetches the full complaint and uses KBEnrichmentManager for richer enrichment.
    """
    supabase = get_supabase()

    try:
        result = (
            supabase.table("complaints")
            .select(
                "complaint_id, status, category, masked_text, "
                "tier_resolved_at, current_tier, branch_id, "
                "customer_feedback_score, compliance_category, "
                "escalation_count, is_duplicate"
            )
            .eq("complaint_id", complaint_id)
            .execute()
        )

        if not result.data:
            logger.warning("[KB] Complaint %s not found — skipping enrichment", complaint_id)
            return

        complaint = result.data[0]
        status    = complaint.get("status", "")

        # Negative signal — customer escalated or reopened
        if status in ("escalated", "reopened", "human_review", "override_closed"):
            logger.info(
                "[KB] Complaint %s has status '%s' — skipping KB add", complaint_id, status
            )
            await _update_queue(complaint_id, added_to_kb=False)
            return

        # Positive signal — still auto_closed after 24 h → implicit acceptance
        resolution_event = {
            "type":             TYPE_AUTO_RESPONSE,
            "resolution_text":  draft_response,
            "confidence_score": confidence_score,
            "agent_action":     None,
        }

        # Use enrichment manager for tier-aware, quality-scored insert
        queue_id = await asyncio.to_thread(
            _manager.enqueue_for_enrichment,
            complaint,
            resolution_event,
        )

        if queue_id:
            # Also directly add to KB (verified=False, admin can review via queue)
            await asyncio.to_thread(
                _add_to_knowledge_base,
                complaint_id     = complaint_id,
                complaint_text   = complaint.get("masked_text", ""),
                resolution_text  = draft_response,
                category         = complaint.get("category", "General Banking"),
                confidence_score = confidence_score,
                tier_level       = int(complaint.get("tier_resolved_at") or tier_level),
            )

        # Mark complaint as auto-response accepted
        try:
            supabase.table("complaints").update({
                "auto_response_accepted": True
            }).eq("complaint_id", complaint_id).execute()
        except Exception:
            pass

        await _update_queue(complaint_id, added_to_kb=bool(queue_id))
        logger.info("[KB] Enrichment complete for %s", complaint_id)

    except Exception as exc:
        logger.exception("[KB] Enrichment failed for %s: %s", complaint_id, exc)


def _add_to_knowledge_base(
    complaint_id: str,
    complaint_text: str,
    resolution_text: str,
    category: str,
    confidence_score: float,
    tier_level: int,
) -> None:
    """Generate embedding and insert into knowledge_base (unverified, pending admin review)."""
    from openai import OpenAI
    from app.core.config import get_settings

    settings = get_settings()
    client   = OpenAI(api_key=settings.openai_api_key)
    supabase = get_supabase()

    embed_resp = client.embeddings.create(
        input      = f"{complaint_text}\n\nResolution: {resolution_text}",
        model      = settings.openai_embedding_model,
        dimensions = settings.openai_embedding_dimension,
    )
    embedding = embed_resp.data[0].embedding

    try:
        supabase.table("knowledge_base").insert({
            "complaint_id":       complaint_id,
            "source_complaint_id": complaint_id,
            "category":           category,
            "resolution_text":    resolution_text,
            "embedding":          embedding,
            "quality_score":      confidence_score,
            "tier_level":         tier_level,
            "source":             "auto_enrichment",
            "verified":           False,
        }).execute()
    except Exception as exc:
        logger.error("[KB] knowledge_base insert failed for %s: %s", complaint_id, exc)


async def _log_to_queue(complaint_id: str, draft_response: str, delay_hours: int) -> None:
    """Persist enrichment intent to kb_enrichment_queue (best-effort)."""
    supabase = get_supabase()
    scheduled_for = (
        datetime.now(timezone.utc) + timedelta(hours=delay_hours)
    ).isoformat()
    try:
        supabase.table("kb_enrichment_queue").insert({
            "complaint_id":    complaint_id,
            "resolution_text": draft_response,
            "scheduled_for":   scheduled_for,
            "processed":       False,
            "added_to_kb":     False,
        }).execute()
    except Exception as exc:
        logger.debug("[KB] kb_enrichment_queue insert failed (may not exist): %s", exc)


async def _update_queue(complaint_id: str, added_to_kb: bool) -> None:
    """Mark queue row as processed (best-effort)."""
    supabase = get_supabase()
    try:
        supabase.table("kb_enrichment_queue").update({
            "processed":    True,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "added_to_kb":  added_to_kb,
        }).eq("complaint_id", complaint_id).eq("processed", False).execute()
    except Exception as exc:
        logger.debug("[KB] kb_enrichment_queue update failed: %s", exc)
