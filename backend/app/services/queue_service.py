"""
Queue Management Service — Manage human-agent work queues by tier.

Priority score formula (higher = more urgent):
  urgency_score   (0-10)  * 3.0
  severity_score  (0-10)  * 2.0
  time_in_queue   (hours) * 0.5   (capped at 24 h contribution)
"""

from datetime import datetime, timezone, timedelta
from app.db.supabase_client import get_supabase
from app.services.agent_assignment_service import find_best_agent


# ── Priority ──────────────────────────────────────────────────────────────────

def _calculate_priority_score(
    urgency_score: float,
    severity_score: float,
    hours_in_queue: float = 0.0,
) -> float:
    time_component = min(hours_in_queue, 24.0) * 0.5
    raw = urgency_score * 3.0 + severity_score * 2.0 + time_component
    return round(raw, 4)


def _estimate_review_time(severity: int) -> int:
    """Estimate review time in minutes based on severity (1-5)."""
    mapping = {1: 5, 2: 8, 3: 12, 4: 20, 5: 30}
    return mapping.get(severity, 12)


# ── Public API ────────────────────────────────────────────────────────────────

def assign_to_queue(
    complaint_id: str,
    tier_level: int,
    urgency_score: float,
    severity: int,
    severity_score: float,
    category: str,
    sla_deadline: str | None = None,
) -> dict:
    """
    Insert complaint into agent_queue.

    Tries to immediately assign to a free agent at tier_level.
    If no agent is available the row is inserted with status=QUEUED.

    Returns the queue row dict including assigned_to and queue_position.

    Called from routing_node (inside the pipeline) — the pipeline already
    guarantees only HUMAN/ESCALATE routes reach this function.
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    priority_score = _calculate_priority_score(urgency_score, severity_score)
    estimated_review_time = _estimate_review_time(severity)

    # ── Check for an existing open queue entry ────────────────────────────
    # Two cases:
    #   • Same tier  → complaint already queued here; skip silently (pipeline re-run).
    #   • Diff tier  → complaint escalated to a new tier; close the old entry first
    #                  so the agent at the new tier can see it.
    existing_result = (
        supabase.table("agent_queue")
        .select("id, tier_level, status")
        .eq("complaint_id", complaint_id)
        .in_("status", ["QUEUED", "ASSIGNED", "IN_REVIEW"])
        .limit(1)
        .execute()
    )

    if existing_result.data:
        existing_row = existing_result.data[0]
        if existing_row["tier_level"] == tier_level:
            # Already queued at this tier — nothing to do.
            return {
                "queue_id":              existing_row["id"],
                "complaint_id":          complaint_id,
                "assigned_to":           None,
                "status":                "SKIPPED_ALREADY_QUEUED",
                "queue_position":        calculate_queue_position(complaint_id, tier_level),
                "priority_score":        priority_score,
                "estimated_review_time": estimated_review_time,
                "sla_deadline":          sla_deadline,
            }
        else:
            # Tier changed (escalation) — mark the old entry as COMPLETED so
            # agents at the old tier no longer see it.
            # ESCALATED is not a valid status (DB constraint: QUEUED|ASSIGNED|IN_REVIEW|COMPLETED).
            supabase.table("agent_queue").update({
                "status":     "COMPLETED",
                "updated_at": now.isoformat(),
            }).eq("id", existing_row["id"]).execute()

    # Try to find an available agent immediately
    agent_id = find_best_agent(
        tier_level=tier_level,
        complaint_category=category,
    )

    status = "ASSIGNED" if agent_id else "QUEUED"

    row = {
        "complaint_id":         complaint_id,
        "tier_level":           tier_level,
        "assigned_to":          agent_id,
        "assigned_at":          now.isoformat() if agent_id else None,
        "priority_score":       priority_score,
        "status":               status,
        "sla_deadline":         sla_deadline,
        "estimated_review_time": estimated_review_time,
        "created_at":           now.isoformat(),
        "updated_at":           now.isoformat(),
    }

    insert_result = supabase.table("agent_queue").insert(row).execute()
    queue_id = insert_result.data[0]["id"] if insert_result.data else None

    # Compute and persist queue_position
    queue_position = calculate_queue_position(complaint_id, tier_level)
    if queue_id:
        supabase.table("agent_queue").update(
            {"queue_position": queue_position}
        ).eq("id", queue_id).execute()

    # Also create an agent_assignments row if immediately assigned
    if agent_id:
        supabase.table("agent_assignments").insert({
            "complaint_id": complaint_id,
            "agent_id":     agent_id,
            "tier_level":   tier_level,
            "assigned_at":  now.isoformat(),
        }).execute()

        # Update complaint record
        supabase.table("complaints").update({
            "assigned_agent_id": agent_id,
            "status":            "pending_review",
            "tier_pending_at":   tier_level,
        }).eq("complaint_id", complaint_id).execute()
    else:
        supabase.table("complaints").update({
            "status":        "pending_review",
            "tier_pending_at": tier_level,
        }).eq("complaint_id", complaint_id).execute()

    return {
        "queue_id":              queue_id,
        "complaint_id":          complaint_id,
        "assigned_to":           agent_id,
        "status":                status,
        "queue_position":        queue_position,
        "priority_score":        priority_score,
        "estimated_review_time": estimated_review_time,
        "sla_deadline":          sla_deadline,
    }


def get_next_complaint(agent_id: str, tier_level: int) -> dict | None:
    """
    Fetch the highest-priority unassigned complaint for an agent.

    Marks it as ASSIGNED and transitions the complaint status to pending_review.
    Returns None if queue is empty.
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    result = (
        supabase.table("agent_queue")
        .select("*")
        .eq("tier_level", tier_level)
        .eq("status", "QUEUED")
        .is_("assigned_to", "null")
        .order("priority_score", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    queue_id = row["id"]
    complaint_id = row["complaint_id"]

    supabase.table("agent_queue").update({
        "assigned_to": agent_id,
        "assigned_at": now.isoformat(),
        "status":      "ASSIGNED",
        "updated_at":  now.isoformat(),
    }).eq("id", queue_id).execute()

    supabase.table("agent_assignments").insert({
        "complaint_id": complaint_id,
        "agent_id":     agent_id,
        "tier_level":   tier_level,
        "assigned_at":  now.isoformat(),
    }).execute()

    supabase.table("complaints").update({
        "assigned_agent_id": agent_id,
    }).eq("complaint_id", complaint_id).execute()

    return {**row, "assigned_to": agent_id, "status": "ASSIGNED"}


def mark_in_review(complaint_id: str, agent_id: str) -> None:
    """Transition queue row to IN_REVIEW and record started_review_at."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    supabase.table("agent_queue").update({
        "status":     "IN_REVIEW",
        "updated_at": now.isoformat(),
    }).eq("complaint_id", complaint_id).eq("assigned_to", agent_id).execute()

    supabase.table("agent_assignments").update({
        "started_review_at": now.isoformat(),
    }).eq("complaint_id", complaint_id).eq("agent_id", agent_id).is_(
        "started_review_at", "null"
    ).execute()

    supabase.table("complaints").update({
        "review_started_at": now.isoformat(),
        "status":            "in_review",
    }).eq("complaint_id", complaint_id).execute()


def complete_queue_entry(complaint_id: str, agent_id: str, action: str) -> None:
    """Mark queue row COMPLETED and store action in agent_assignments."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    supabase.table("agent_queue").update({
        "status":     "COMPLETED",
        "updated_at": now.isoformat(),
    }).eq("complaint_id", complaint_id).eq("assigned_to", agent_id).execute()

    # Calculate time_spent_seconds
    assign_result = (
        supabase.table("agent_assignments")
        .select("started_review_at, assigned_at")
        .eq("complaint_id", complaint_id)
        .eq("agent_id", agent_id)
        .order("assigned_at", desc=True)
        .limit(1)
        .execute()
    )

    time_spent = None
    if assign_result.data:
        start_str = assign_result.data[0].get("started_review_at") or assign_result.data[0].get("assigned_at")
        if start_str:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_spent = int((now - start_dt).total_seconds())

    supabase.table("agent_assignments").update({
        "completed_at":       now.isoformat(),
        "action_taken":       action,
        "time_spent_seconds": time_spent,
    }).eq("complaint_id", complaint_id).eq("agent_id", agent_id).is_(
        "completed_at", "null"
    ).execute()


def calculate_queue_position(complaint_id: str, tier_level: int) -> int:
    """
    Return the 1-based queue position of complaint_id within its tier's QUEUED rows.

    Position is determined by descending priority_score — the highest-priority
    complaint is position 1.
    """
    supabase = get_supabase()

    result = (
        supabase.table("agent_queue")
        .select("complaint_id, priority_score")
        .eq("tier_level", tier_level)
        .in_("status", ["QUEUED", "ASSIGNED"])
        .order("priority_score", desc=True)
        .execute()
    )

    for idx, row in enumerate(result.data or [], start=1):
        if row["complaint_id"] == complaint_id:
            return idx
    return 1


def rebalance_queue(tier_level: int) -> dict:
    """
    Redistribute open queue entries if agents went offline or SLA is imminent.

    - Unassign complaints from agents no longer active (simulated by checking
      whether agent_id is still in tier mapping).
    - Boost priority_score for complaints approaching SLA deadline.

    Returns a summary of changes made.
    """
    from app.core.config import get_settings
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    settings = get_settings()

    active_agents = set(settings.tier_agent_mapping.get(tier_level, []))

    result = (
        supabase.table("agent_queue")
        .select("*")
        .eq("tier_level", tier_level)
        .in_("status", ["ASSIGNED", "IN_REVIEW"])
        .execute()
    )

    reassigned = 0
    boosted = 0

    for row in result.data or []:
        queue_id     = row["id"]
        assigned_to  = row.get("assigned_to")
        sla_str      = row.get("sla_deadline")
        priority     = row.get("priority_score", 0)

        # Reassign if agent is offline
        if assigned_to and assigned_to not in active_agents:
            supabase.table("agent_queue").update({
                "assigned_to": None,
                "assigned_at": None,
                "status":      "QUEUED",
                "updated_at":  now.isoformat(),
            }).eq("id", queue_id).execute()
            reassigned += 1

        # Boost priority if SLA breach imminent (< 2 hours)
        if sla_str:
            sla_dt = datetime.fromisoformat(sla_str.replace("Z", "+00:00"))
            hours_until_breach = (sla_dt - now).total_seconds() / 3600
            if 0 < hours_until_breach < 2:
                supabase.table("agent_queue").update({
                    "priority_score": priority + 20.0,
                    "updated_at":     now.isoformat(),
                }).eq("id", queue_id).execute()
                boosted += 1

    return {"tier_level": tier_level, "reassigned": reassigned, "priority_boosted": boosted}
