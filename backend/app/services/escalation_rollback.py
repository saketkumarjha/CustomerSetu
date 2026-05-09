"""
Escalation Rollback Handler

Called when a partial pipeline run fails mid-escalation.
Restores the complaint to the pre-escalation tier and routes to human review.
"""

from app.db.supabase_client import get_supabase
from app.services.escalation_logger import mark_escalation_failed


def rollback_escalation(
    complaint_id: str,
    from_tier: int,
    error: str,
) -> dict:
    """
    Restore complaint.current_tier to from_tier and clear is_escalating flag.
    Logs a FAILED escalation entry for the audit trail.
    """
    supabase = get_supabase()

    supabase.table("complaints").update({
        "current_tier": from_tier,
        "is_escalating": False,
    }).eq("complaint_id", complaint_id).execute()

    mark_escalation_failed(complaint_id, from_tier, error)

    return {
        "rolled_back": True,
        "restored_tier": from_tier,
        "error": error,
    }
