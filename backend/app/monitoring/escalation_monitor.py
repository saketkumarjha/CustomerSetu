"""
Escalation Performance Monitor

Provides a health snapshot of active escalations, loop detections,
and recent escalation paths.  Intended for the ops dashboard.

Call get_escalation_health() to retrieve the current state.
"""

from app.db.supabase_client import get_supabase


def get_escalation_health() -> dict:
    """
    Returns:
      active_escalations : int   — complaints with is_escalating = True
      loop_detections    : int   — complaints where a loop was flagged
      alarms             : list  — CRITICAL / WARNING messages
      recent_escalations : list  — last 10 escalated complaints (summary)
    """
    supabase = get_supabase()

    active_res = (
        supabase.table("complaints")
        .select("complaint_id", count="exact")
        .eq("is_escalating", True)
        .execute()
    )
    active_count = active_res.count or 0

    loop_res = (
        supabase.table("complaints")
        .select("complaint_id", count="exact")
        .eq("escalation_loop_detected", True)
        .execute()
    )
    loop_count = loop_res.count or 0

    recent_res = (
        supabase.table("complaints")
        .select("complaint_id, escalation_count, escalation_path, max_tier_reached, last_escalation_at")
        .gt("escalation_count", 0)
        .order("last_escalation_at", desc=True)
        .limit(10)
        .execute()
    )

    return {
        "active_escalations": active_count,
        "loop_detections": loop_count,
        "alarms": _check_alarms(active_count, loop_count),
        "recent_escalations": recent_res.data or [],
    }


def _check_alarms(active_count: int, loop_count: int) -> list:
    alarms = []
    if active_count > 100:
        alarms.append({
            "level": "CRITICAL",
            "message": f"High concurrent escalations: {active_count}. Check backend load.",
        })
    if loop_count > 0:
        alarms.append({
            "level": "CRITICAL",
            "message": f"Loop detected in {loop_count} complaint(s). Investigate escalation logic.",
        })
    return alarms
