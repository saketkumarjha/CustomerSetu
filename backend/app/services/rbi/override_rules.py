"""
RBI Supervisor Override Rules

These rules are enforced by the Supervisor AFTER all agents complete
and BEFORE the confidence threshold check.

Override rules take precedence over everything including confidence score.
A complaint that would pass the confidence threshold for auto-respond
will still be forced to human review if an override rule applies.

This is the RBI compliance enforcement layer.
"""

from app.services.rbi.categories import (
    RBICategory,
    SUPERVISOR_OVERRIDE_ALWAYS_HUMAN,
)


def check_override_rules(
    compliance_category: str,
    sentiment: str,
    severity: int,
    urgency_score: float,
    escalation_flag: bool,
    grounding_assessment: str,
) -> dict:
    """
    Check all override rules and return the override decision.

    Args:
        compliance_category:  RBI category from Compliance Agent
        sentiment:            Emotion from Sentiment Agent
        severity:             1-5 from Severity Agent
        urgency_score:        1-10 from Sentiment Agent
        escalation_flag:      bool from Sentiment Agent
        grounding_assessment: SAFE_TO_SEND | VERIFY_BEFORE_SEND | DO_NOT_SEND

    Returns dict with:
        override_triggered:  bool — did any rule fire?
        override_reason:     str — which rule fired (for XAI)
        forced_route:        "human_review" | None
        override_rules_hit:  list of rule names that fired
    """
    rules_hit = []

    # ── Rule 1: RBI Category Override ────────────────────────────────────
    # Certain RBI categories are NEVER auto-responded
    # regardless of confidence, severity, or anything else
    try:
        cat_enum = RBICategory(compliance_category)
        if cat_enum in SUPERVISOR_OVERRIDE_ALWAYS_HUMAN:
            rules_hit.append(
                f"RBI_CATEGORY_OVERRIDE: {compliance_category} requires "
                f"mandatory human review per RBI guidelines"
            )
    except ValueError:
        pass

    # ── Rule 2: Furious Sentiment Override ────────────────────────────────
    # Extreme emotional distress requires human empathy
    if sentiment == "Furious":
        rules_hit.append(
            "SENTIMENT_OVERRIDE: Customer sentiment is Furious — "
            "AI auto-response is inappropriate. Human empathy required."
        )

    # ── Rule 3: Critical Severity Override ───────────────────────────────
    # Severity 5 (Emergency) always needs human review
    if severity >= 5:
        rules_hit.append(
            "SEVERITY_OVERRIDE: Severity 5 (Emergency) — "
            "mandatory human review for critical complaints"
        )

    # ── Rule 4: Escalation Flag Override ─────────────────────────────────
    # Sentiment Agent detected escalation signals (RBI threats, legal threats)
    if escalation_flag:
        rules_hit.append(
            "ESCALATION_OVERRIDE: Customer has signalled escalation intent "
            "(RBI complaint, legal action, media) — human intervention required"
        )

    # ── Rule 5: Grounding DO_NOT_SEND Override ───────────────────────────
    # Grounding Agent flagged the draft as unsafe to send
    if grounding_assessment == "DO_NOT_SEND":
        rules_hit.append(
            "GROUNDING_OVERRIDE: Grounding Agent flagged draft as DO_NOT_SEND — "
            "draft contains serious compliance or factual issues"
        )

    # ── Rule 6: High Urgency Override ────────────────────────────────────
    # Urgency score 10/10 always requires human attention
    if urgency_score >= 10:
        rules_hit.append(
            "URGENCY_OVERRIDE: Maximum urgency score (10/10) — "
            "immediate human attention required"
        )

    override_triggered = len(rules_hit) > 0

    return {
        "override_triggered": override_triggered,
        "override_reason": " | ".join(rules_hit) if rules_hit else None,
        "forced_route": "human_review" if override_triggered else None,
        "override_rules_hit": rules_hit,
    }