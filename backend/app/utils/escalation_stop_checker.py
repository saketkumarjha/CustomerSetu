from app.core.config import get_settings


def should_stop_escalating(
    complaint_id: str,
    current_tier: int,
    confidence: float,
    escalation_count: int,
    escalation_decision: str,
    loop_detected: bool = False,
) -> dict:
    """
    Determine whether the auto-escalation loop should stop.

    Stop conditions (checked in priority order):
      1. confidence >= 0.95  → auto_respond (success)
      2. tier >= max          → human_review (can't escalate further)
      3. escalation_count >=  max_iterations → human_review (runaway protection)
      4. loop_detected        → human_review (safety)
      5. HUMAN_AT_CURRENT_TIER from Agent 10.5 → human_review
    """
    settings = get_settings()

    if confidence >= 0.95:
        return {"should_stop": True, "stop_reason": "CONFIDENCE_MET", "final_action": "auto_respond"}

    if current_tier >= settings.max_escalation_tier:
        return {"should_stop": True, "stop_reason": "MAX_TIER_REACHED", "final_action": "human_review"}

    if escalation_count >= settings.max_escalation_iterations:
        return {"should_stop": True, "stop_reason": "MAX_ITERATIONS_REACHED", "final_action": "human_review"}

    if loop_detected:
        return {"should_stop": True, "stop_reason": "LOOP_DETECTED", "final_action": "human_review"}

    if escalation_decision == "HUMAN_AT_CURRENT_TIER":
        return {"should_stop": True, "stop_reason": "HUMAN_AT_CURRENT_TIER", "final_action": "human_review"}

    return {"should_stop": False, "stop_reason": None, "final_action": None}
