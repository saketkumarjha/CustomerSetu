"""
Risk-Aware Router — Modified for Agent 10.5 Compatibility

Agent 10: Primary Router (Modified)
-------------------------------------
This is NOT a GPT-4o call. It is a deterministic decision engine.

NEW Decision flow:
1. Check RBI override rules
   - FRAUD                → force tier_hint=4, route=HUMAN
   - Furious sentiment    → route=HUMAN
   - Severity 5           → route=HUMAN
   If any override fires  → return immediately, skip confidence check

2. Confidence gate (single threshold: 0.95)
   - confidence >= 0.95   → route=AUTO,    pipeline ends here
   - confidence <  0.95   → route=ESCALATE, hand off to Agent 10.5

3. Risk score is ALWAYS calculated (for XAI audit + Agent 10.5 pass-through)
   but it does NOT affect routing in Agent 10.

Output keys:
  route            : "AUTO" | "HUMAN" | "ESCALATE"
  confidence       : float
  sla_deadline     : ISO datetime string or None
  override_triggered : bool
  override_rules   : list[str]
  tier_hint        : int | None  (4 when fraud override, else None — Agent 10.5 decides)
  risk_score       : float       (pass-through for Agent 10.5)
  risk_breakdown   : dict        (pass-through for Agent 10.5)
  reasoning        : str         (XAI audit trail)

Why deterministic (not LLM-based):
  Routing decisions that affect SLAs, regulatory compliance, and customer
  outcomes must be fully auditable and reproducible. An LLM might make
  different routing decisions for identical inputs. A deterministic algorithm
  always produces the same output — required for RBI audit compliance.
"""

from datetime import datetime, timezone
from app.services.rbi.override_rules import check_override_rules
from app.services.rbi.tat_rules import calculate_tat_deadline
from app.services.agents.resolution_agent import CATEGORY_CONFIDENCE_THRESHOLDS

# ── Constants ────────────────────────────────────────────────────────────────

AUTO_RESPOND_CONFIDENCE_GATE = 0.95  # Below this → Agent 10.5 decides tier

# Override categories that imply minimum Tier 4 (Head Office / Nodal Officer)
FRAUD_CATEGORIES = {
    "UNAUTHORIZED_TRANSACTION_FRAUD",
    "PHISHING_FRAUD",
    "ACCOUNT_TAKEOVER",
}


# ── Risk Score (kept for XAI + Agent 10.5 pass-through) ─────────────────────

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

    NOTE: This score no longer drives the routing decision in Agent 10.
    It is calculated purely for:
      - XAI / audit trail (agent_decisions table)
      - Pass-through to Agent 10.5 (Escalation Analyzer)

    Risk score formula (max = 1.0):
      severity   : severity_score/10  * 0.30
      confidence : (1 - confidence)   * 0.25
      rbi        : 0.25 if reportable
      urgency    : urgency_score/10   * 0.10
      grounding  : (1 - grounding)    * 0.10
    """
    severity_component   = (severity_score / 10) * 0.30
    confidence_component = (1 - confidence_score) * 0.25
    rbi_component        = 0.25 if is_rbi_reportable else 0.0
    urgency_component    = (urgency_score / 10) * 0.10
    grounding_component  = (1 - grounding_score) * 0.10

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
            "severity_component":   round(severity_component, 4),
            "confidence_component": round(confidence_component, 4),
            "rbi_component":        round(rbi_component, 4),
            "urgency_component":    round(urgency_component, 4),
            "grounding_component":  round(grounding_component, 4),
        },
    }


# ── Main Routing Decision ────────────────────────────────────────────────────

def make_routing_decision(
    # Complaint identity
    complaint_id: str,
    category: str,
    # From Compliance Agent (Agent 5)
    compliance_category: str,
    is_rbi_reportable: bool,
    # From Sentiment Agent (Agent 4)
    sentiment: str,
    # From Severity Agent (Agent 6)
    severity: int,
    severity_score: float,
    urgency_score: float,
    escalation_flag: bool,
    # From Resolution Agent (Agent 8)
    confidence_score: float,
    # From Grounding Agent (Agent 9)
    grounding_score: float,
    grounding_assessment: str,
) -> dict:
    """
    Make the primary routing decision for a complaint.

    Returns AUTO, HUMAN (with tier_hint), or ESCALATE (to Agent 10.5).
    Decision is fully deterministic — same inputs always produce same output.
    """
    reasoning_steps = []
    routing_factors = []

    # ── Step 1: Override Rules ───────────────────────────────────────────────
    override = check_override_rules(
        compliance_category=compliance_category,
        sentiment=sentiment,
        severity=severity,
        urgency_score=urgency_score,
        escalation_flag=escalation_flag,
        grounding_assessment=grounding_assessment,
    )
    override_triggered  = override.get("override_triggered", False)
    override_rules_hit  = override.get("override_rules_hit", [])

    if override_triggered:
        for rule in override_rules_hit:
            reasoning_steps.append(f"OVERRIDE TRIGGERED: {rule}")
            routing_factors.append(rule)

        # Determine tier_hint from override type
        # Fraud → minimum Tier 4 (Head Office / Nodal Officer)
        # Furious / Severity 5 → Human review, Agent 10.5 will assign tier
        is_fraud_override = compliance_category in FRAUD_CATEGORIES
        tier_hint = 4 if is_fraud_override else None

        tat = calculate_tat_deadline(compliance_category)
        sla_deadline = tat["tat_deadline_iso"]

        # Risk score — still calculated for audit trail
        risk_result = calculate_risk_score(
            severity_score=severity_score,
            confidence_score=confidence_score,
            urgency_score=urgency_score,
            is_rbi_reportable=is_rbi_reportable,
            grounding_score=grounding_score,
            escalation_flag=escalation_flag,
        )

        reasoning = (
            f"ROUTING DECISION: HUMAN (Override)\n"
            f"Complaint ID: {complaint_id}\n"
            f"Override rules triggered: {len(override_rules_hit)}\n"
            + "\n".join(f"  {i+1}. {r}" for i, r in enumerate(override_rules_hit))
            + f"\n\nTier hint: {'4 (Fraud — Head Office minimum)' if tier_hint == 4 else 'None (Agent 10.5 will decide tier)'}\n"
            f"Confidence check: SKIPPED (override takes precedence)\n"
            f"SLA deadline: {sla_deadline}\n"
            f"Risk score: {risk_result['risk_score']} (audit only — not used for routing)\n"
            f"Penalty: {tat.get('penalty_description', 'N/A')}"
        )

        return {
            "route":               "HUMAN",
            "confidence":          confidence_score,
            "sla_deadline":        sla_deadline,
            "override_triggered":  True,
            "override_rules":      override_rules_hit,
            "tier_hint":           tier_hint,
            "risk_score":          risk_result["risk_score"],
            "risk_breakdown":      risk_result["breakdown"],
            "routing_factors":     routing_factors,
            "confidence_gate_applied": False,
            "reasoning":           reasoning,
        }

    reasoning_steps.append("No override rules triggered. Proceeding to confidence gate.")

    # ── Step 2: Confidence Gate ──────────────────────────────────────────────
    # Single threshold: 0.95
    # Above → AUTO_RESPOND (pipeline ends here, no Agent 10.5)
    # Below → ESCALATE   (Agent 10.5 will analyze tier + resolution path)

    # TAT deadline — always calculated for RBI compliance tracking
    tat_category = compliance_category if is_rbi_reportable else "NOT_APPLICABLE"
    tat          = calculate_tat_deadline(tat_category)
    sla_deadline = tat["tat_deadline_iso"] if is_rbi_reportable else None

    # Risk score — calculated for audit + Agent 10.5 pass-through
    risk_result = calculate_risk_score(
        severity_score=severity_score,
        confidence_score=confidence_score,
        urgency_score=urgency_score,
        is_rbi_reportable=is_rbi_reportable,
        grounding_score=grounding_score,
        escalation_flag=escalation_flag,
    )
    risk_score     = risk_result["risk_score"]
    risk_breakdown = risk_result["breakdown"]

    if confidence_score >= AUTO_RESPOND_CONFIDENCE_GATE:
        # ── AUTO RESPOND ─────────────────────────────────────────────────────
        reasoning_steps.append(
            f"Confidence {confidence_score:.1%} >= {AUTO_RESPOND_CONFIDENCE_GATE:.0%} gate. AUTO RESPOND."
        )

        reasoning = (
            f"ROUTING DECISION: AUTO\n"
            f"Complaint ID: {complaint_id}\n"
            f"Confidence: {confidence_score:.1%} — passed {AUTO_RESPOND_CONFIDENCE_GATE:.0%} gate\n"
            f"Category: {category}\n"
            f"Agent 10.5: NOT called\n"
            f"Risk score: {risk_score} (audit only)\n"
            + "\n".join(f"  {i+1}. {step}" for i, step in enumerate(reasoning_steps))
        )

        return {
            "route":               "AUTO",
            "confidence":          confidence_score,
            "sla_deadline":        sla_deadline,
            "override_triggered":  False,
            "override_rules":      [],
            "tier_hint":           None,
            "risk_score":          risk_score,
            "risk_breakdown":      risk_breakdown,
            "routing_factors":     routing_factors,
            "confidence_gate_applied": True,
            "reasoning":           reasoning,
        }

    else:
        # ── ESCALATE → Agent 10.5 ────────────────────────────────────────────
        reasoning_steps.append(
            f"Confidence {confidence_score:.1%} < {AUTO_RESPOND_CONFIDENCE_GATE:.0%} gate. "
            f"Handing off to Agent 10.5 (Escalation Analyzer)."
        )

        reasoning = (
            f"ROUTING DECISION: ESCALATE → Agent 10.5\n"
            f"Complaint ID: {complaint_id}\n"
            f"Confidence: {confidence_score:.1%} — below {AUTO_RESPOND_CONFIDENCE_GATE:.0%} gate\n"
            f"Category: {category}\n"
            f"Risk score: {risk_score} (passed to Agent 10.5)\n"
            f"RBI reportable: {is_rbi_reportable}\n"
            f"Severity: {severity} | Sentiment: {sentiment}\n"
            + "\n".join(f"  {i+1}. {step}" for i, step in enumerate(reasoning_steps))
            + f"\nAgent 10.5 will determine: tier (Branch/Zone/Region/HO), "
            f"resolution path, and human assignment."
        )

        return {
            "route":               "ESCALATE",
            "confidence":          confidence_score,
            "sla_deadline":        sla_deadline,
            "override_triggered":  False,
            "override_rules":      [],
            "tier_hint":           None,      # Agent 10.5 decides tier
            "risk_score":          risk_score,
            "risk_breakdown":      risk_breakdown,
            "routing_factors":     routing_factors,
            "confidence_gate_applied": True,
            "reasoning":           reasoning,
        }