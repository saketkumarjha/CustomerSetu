"""
Status Service — Centralized complaint status transitions.

Valid transitions from pending_review:
  pending_review        → in_review             (agent opened complaint)
  in_review             → auto_closed            (agent accepted / edited)
  in_review             → awaiting_agent_response (agent rejected, writing own response)
  in_review             → escalating             (manual escalation triggered)
  pending_review        → overdue_review         (SLA breach)
"""

from datetime import datetime, timezone
from app.db.supabase_client import get_supabase

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending_review":          {"in_review", "overdue_review"},
    "in_review":               {"auto_closed", "awaiting_agent_response", "escalating"},
    "awaiting_agent_response": {"auto_closed"},
    "escalating":              {"pending_review", "auto_closed"},
    "overdue_review":          {"in_review", "escalating"},
}


def update_status(
    complaint_id: str,
    new_status: str,
    changed_by: str = "SYSTEM",
    metadata: dict | None = None,
) -> dict:
    """
    Transition a complaint to new_status.

    Validates the transition, updates the complaints table, and writes a row
    to complaint_status_history.

    Returns the updated status dict or raises ValueError on invalid transition.
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    result = (
        supabase.table("complaints")
        .select("complaint_id, status")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    current_status = result.data[0].get("status", "")

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {current_status!r} → {new_status!r}. "
            f"Allowed from {current_status!r}: {sorted(allowed)}"
        )

    update_payload: dict = {"status": new_status}

    if new_status == "in_review":
        update_payload["review_started_at"] = now.isoformat()
    elif new_status in {"auto_closed", "awaiting_agent_response"}:
        update_payload["human_review_completed_at"] = now.isoformat()

    supabase.table("complaints").update(update_payload).eq(
        "complaint_id", complaint_id
    ).execute()

    supabase.table("complaint_status_history").insert({
        "complaint_id": complaint_id,
        "old_status":   current_status,
        "new_status":   new_status,
        "changed_by":   changed_by,
        "changed_at":   now.isoformat(),
        "metadata":     metadata or {},
    }).execute()

    return {
        "complaint_id": complaint_id,
        "old_status":   current_status,
        "new_status":   new_status,
        "changed_at":   now.isoformat(),
        "changed_by":   changed_by,
    }
