"""
Metrics Service — Track agent review timing and quality signals.
"""

from datetime import datetime, timezone
from app.db.supabase_client import get_supabase


def track_review_started(complaint_id: str, agent_id: str) -> None:
    """
    Record the moment an agent opens a complaint for review.
    Updates the agent_queue and agent_assignments rows.
    """
    from app.services.queue_service import mark_in_review
    mark_in_review(complaint_id, agent_id)


def track_review_completed(
    complaint_id: str,
    agent_id: str,
    action: str,
) -> None:
    """
    Record the moment an agent completes a review.
    Delegates time-spent calculation to queue_service.complete_queue_entry.
    """
    from app.services.queue_service import complete_queue_entry
    complete_queue_entry(complaint_id, agent_id, action)


def calculate_agent_efficiency(
    agent_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """
    Compute efficiency stats for an agent over a date range.

    date_from / date_to: ISO strings (inclusive). Defaults to all time.
    """
    supabase = get_supabase()

    query = (
        supabase.table("agent_assignments")
        .select("action_taken, time_spent_seconds, completed_at")
        .eq("agent_id", agent_id)
        .not_.is_("completed_at", "null")
    )
    if date_from:
        query = query.gte("completed_at", date_from)
    if date_to:
        query = query.lte("completed_at", date_to)

    result = query.execute()
    rows = result.data or []

    if not rows:
        return {
            "agent_id": agent_id,
            "total_reviewed": 0,
            "avg_review_time_seconds": None,
            "acceptance_rate": None,
            "edit_rate": None,
            "rejection_rate": None,
            "escalation_rate": None,
        }

    total = len(rows)
    counts = {"ACCEPT": 0, "EDIT": 0, "REJECT": 0, "ESCALATE": 0}
    times = []

    for row in rows:
        action = row.get("action_taken")
        if action in counts:
            counts[action] += 1
        t = row.get("time_spent_seconds")
        if t:
            times.append(t)

    avg_time = round(sum(times) / len(times)) if times else None

    return {
        "agent_id":                agent_id,
        "total_reviewed":          total,
        "avg_review_time_seconds": avg_time,
        "acceptance_rate":         round(counts["ACCEPT"] / total, 4),
        "edit_rate":               round(counts["EDIT"] / total, 4),
        "rejection_rate":          round(counts["REJECT"] / total, 4),
        "escalation_rate":         round(counts["ESCALATE"] / total, 4),
    }
