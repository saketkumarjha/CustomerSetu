"""
Risk-Aware Router — Final Supervisor Decision

This is NOT a GPT-4o call. It is the Supervisor's deterministic
decision engine that combines all agent signals into a final routing decision.

Decision flow:
1. Check RBI override rules → if triggered → HUMAN_REVIEW (no further checks)
2. Check confidence vs per-category threshold → if below → HUMAN_REVIEW
3. Calculate risk score from all signals → if above threshold → HUMAN_REVIEW
4. All checks pass → AUTO_RESPOND

Why deterministic (not LLM-based):
  Routing decisions that affect SLAs, regulatory compliance, and customer
  outcomes must be fully auditable and reproducible. An LLM might make
  different routing decisions for identical inputs. A deterministic algorithm
  always produces the same output for the same inputs — required for
  RBI audit compliance.
"""

from datetime import datetime, timezone
from app.services.rbi.override_rules import check_override_rules
from app.services.rbi.tat_rules import calculate_tat_deadline
from app.services.agents.resolution_agent import CATEGORY_CONFIDENCE_THRESHOLDS
from app.services.auto_responder import determine_response_tier

def calculate_risk_score(
    severity_score: float,
    confidence_score: float,
    urgency_score: float,
    is_rbi_reportable: bool,
    grounding_score: float,
    escalation_flag: bool,
) -> dict:
    """
    Calculate composite risk score from all upstream agent signals.

    Risk score formula (max = 1.0):
      severity component:    severity_score/10 * 0.30  (30% weight)
      confidence component:  (1 - confidence) * 0.25   (25% weight)
      rbi component:         0.25 if RBI reportable     (25% weight)
      urgency component:     urgency_score/10 * 0.10   (10% weight)
      grounding component:   (1 - grounding) * 0.10    (10% weight)

    Returns dict with score and breakdown for XAI.
    """
    severity_component = (severity_score / 10) * 0.30
    confidence_component = (1 - confidence_score) * 0.25
    rbi_component = 0.25 if is_rbi_reportable else 0.0
    urgency_component = (urgency_score / 10) * 0.10
    grounding_component = (1 - grounding_score) * 0.10

    total = (
        severity_component
        + confidence_component
        + rbi_component
        + urgency_component
        + grounding_component
    )
    total = min(1.0, round(total, 4))

    return {
        "risk_score": total,
        "breakdown": {
            "severity_component": round(severity_component, 4),
            "confidence_component": round(confidence_component, 4),
            "rbi_component": round(rbi_component, 4),
            "urgency_component": round(urgency_component, 4),
            "grounding_component": round(grounding_component, 4),
        },
    }


def make_routing_decision(
    # From pipeline state
    complaint_id: str,
    category: str,
    compliance_category: str,
    is_rbi_reportable: bool,
    sentiment: str,
    severity: int,
    severity_score: float,
    urgency_score: float,
    escalation_flag: bool,
    confidence_score: float,
    grounding_score: float,
    grounding_assessment: str,
) -> dict:
    """
    Make the final routing decision for a complaint.

    Decision is fully deterministic — same inputs always produce same output.
    Every decision point is logged for XAI and RBI audit trail.

    Returns complete routing decision with XAI reasoning.
    """
    reasoning_steps = []
    routing_factors = []

    # ── Step 1: Check override rules ──────────────────────────────────────
    override = check_override_rules(
        compliance_category=compliance_category,
        sentiment=sentiment,
        severity=severity,
        urgency_score=urgency_score,
        escalation_flag=escalation_flag,
        grounding_assessment=grounding_assessment,
    )
    override_triggered = override.get("override_triggered", False)
    override_rules_hit = override.get("override_rules_hit", [])

    if override_triggered:
        # Override fires — skip all other checks
        # RBI compliance always wins
        for rule in override_rules_hit:
            reasoning_steps.append(f"🚨 OVERRIDE: {rule}")
            routing_factors.append(rule)

        tat = calculate_tat_deadline(compliance_category)
        sla_hours = tat["sla_hours"]
        tat_deadline = tat["tat_deadline_iso"]
        penalty_info = tat["penalty_description"]

        reasoning = (
            f"ROUTING DECISION: HUMAN_REVIEW (Supervisor Override)\n"
            f"Override rules triggered: {len(override_rules_hit)}\n"
            + "\n".join(f"  {i+1}. {r}" for i, r in enumerate(override_rules_hit))
            + f"\n\nSLA: {tat['sla_label']}\n"
            f"Deadline: {tat_deadline}\n"
            f"Penalty: {penalty_info}\n"
            f"Note: Tier logic check was skipped due to override."
        )

        return {
            "route": "human_review",
            "tier": "human_review",
            "tier_number": 3,
            "routing_reason": "supervisor_override",
            "risk_score": 1.0,
            "risk_breakdown": {},
            "sla_hours": sla_hours,
            "rbi_tat_deadline": tat_deadline,
            "penalty_per_day": tat.get("penalty_per_day", 0),
            "override_triggered": True,
            "override_rules": override_rules_hit,
            "confidence_check_skipped": True,
            "confidence_passed": False,
            "risk_passed": False,
            "routing_factors": routing_factors,
            "safety_blocks": ["Override triggered"],
            "reasoning": reasoning,
        }

    reasoning_steps.append("✓ No override rules triggered. Proceeding to tier decision.")

    # ── Step 2: Tiered System ───────────────────────────────────────────
    tier_result = determine_response_tier(
        confidence_score=confidence_score,
        severity=severity,
        sentiment=sentiment,
        is_rbi_reportable=is_rbi_reportable,
        compliance_category=compliance_category,
        grounding_score=grounding_score,
        grounding_assessment=grounding_assessment,
    )

    tier = tier_result["tier"]
    tier_number = tier_result["tier_number"]
    final_sla = tier_result["sla_hours"]

    if tier in ("full_auto", "shadow"):
        route = "auto_respond"
    else:
        route = "human_review"

    # ── Step 3: Risk Score calculation ──────────────────────────────────
    risk_result = calculate_risk_score(
        severity_score=severity_score,
        confidence_score=confidence_score,
        urgency_score=urgency_score,
        is_rbi_reportable=is_rbi_reportable,
        grounding_score=grounding_score,
        escalation_flag=escalation_flag,
    )
    risk_score = risk_result["risk_score"]
    risk_breakdown = risk_result["breakdown"]

    tat = calculate_tat_deadline(compliance_category if route != "auto_respond" else "NOT_APPLICABLE")
    tat_deadline = tat["tat_deadline_iso"] if is_rbi_reportable and route != "auto_respond" else None

    category_threshold = CATEGORY_CONFIDENCE_THRESHOLDS.get(category, 0.80)
    confidence_passed = confidence_score >= category_threshold
    risk_passed = risk_score < 0.60

    reasoning = (
        f"ROUTING DECISION: {route.upper()} — TIER {tier_number} ({tier.upper()})\n"
        f"Tier reason: {tier_result['reason']}\n"
        + (f"Safety blocks: {'; '.join(tier_result['safety_blocks'])}\n"
           if tier_result.get('safety_blocks') else "")
        + f"Confidence: {confidence_score:.0%}\n"
        + "\n".join(f"  {i+1}. {step}" for i, step in enumerate(reasoning_steps))
        + f"\nRisk score: {risk_score:.3f}"
    )

    return {
        "route": route,
        "tier": tier,
        "tier_number": tier_number,
        "routing_reason": tier_result["reason"],
        "risk_score": risk_score,
        "risk_breakdown": risk_breakdown,
        "sla_hours": final_sla,
        "rbi_tat_deadline": tat_deadline,
        "penalty_per_day": tat.get("penalty_per_day", 0),
        "override_triggered": False,
        "override_rules": [],
        "confidence_check_skipped": False,
        "confidence_passed": confidence_passed,
        "risk_passed": risk_passed,
        "routing_factors": routing_factors,
        "safety_blocks": tier_result.get("safety_blocks", []),
        "reasoning": reasoning,
    }