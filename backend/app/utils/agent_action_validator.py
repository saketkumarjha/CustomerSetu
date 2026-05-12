"""
Agent Action Validator — Validate agent actions before processing.
"""

from app.db.supabase_client import get_supabase
from app.core.config import get_settings

MAX_INTERNAL_TIER = 4


def validate_action(
    complaint_id: str,
    agent_id: str,
    action: str,
    payload: dict,
) -> tuple[bool, str]:
    """
    Validate whether an agent is allowed to submit action for complaint_id.

    Returns (True, "") on success or (False, error_message) on failure.
    """
    supabase = get_supabase()

    # 1. Fetch complaint
    result = (
        supabase.table("complaints")
        .select("complaint_id, status, assigned_agent_id, current_tier")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not result.data:
        return False, f"Complaint {complaint_id} not found"

    c = result.data[0]
    current_status = c.get("status", "")
    assigned_agent = c.get("assigned_agent_id")
    current_tier   = c.get("current_tier", 1)

    # 2. Complaint must be in an actionable state.
    #    awaiting_agent_response is also valid: agent may accept/edit after an initial reject.
    actionable = {"in_review", "pending_review", "awaiting_agent_response", "human_review"}
    if current_status not in actionable:
        return False, (
            f"Complaint is in status '{current_status}'. "
            f"Actions only allowed when status is one of: {', '.join(sorted(actionable))}."
        )

    # 3. Must be the assigned agent
    if assigned_agent and assigned_agent != agent_id:
        return False, (
            f"Complaint is assigned to agent '{assigned_agent}', "
            f"not '{agent_id}'. Cannot take action."
        )

    # 4. Action-specific payload checks
    if action == "EDIT":
        edited = payload.get("edited_response", "")
        if not edited or not edited.strip():
            return False, "EDIT action requires a non-empty 'edited_response'."

    elif action == "REJECT":
        reason = payload.get("rejection_reason", "")
        if not reason or not reason.strip():
            return False, "REJECT action requires a non-empty 'rejection_reason'."

    elif action == "MANUAL_ESCALATE":
        target_tier = payload.get("escalation_target_tier")
        if target_tier is None:
            return False, "MANUAL_ESCALATE requires 'escalation_target_tier'."
        if not isinstance(target_tier, int):
            return False, "'escalation_target_tier' must be an integer."
        if target_tier <= current_tier:
            return False, (
                f"Target tier ({target_tier}) must be greater than current tier ({current_tier})."
            )
        if target_tier > MAX_INTERNAL_TIER:
            return False, (
                f"Target tier ({target_tier}) exceeds maximum internal tier ({MAX_INTERNAL_TIER})."
            )

    elif action not in {"ACCEPT", "EDIT", "REJECT", "MANUAL_ESCALATE"}:
        return False, f"Unknown action '{action}'. Must be ACCEPT, EDIT, REJECT, or MANUAL_ESCALATE."

    # 5. Agent must be authorised for this tier
    settings = get_settings()
    tier_agents = settings.tier_agent_mapping.get(current_tier, [])
    if tier_agents and agent_id not in tier_agents:
        return False, (
            f"Agent '{agent_id}' is not authorised for Tier {current_tier}."
        )

    return True, ""
