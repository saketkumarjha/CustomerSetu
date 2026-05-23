"""
Agent 10.5 — Escalation Decision Analyzer

Triggered ONLY when Agent 10 (routing_agent) returns route == "ESCALATE"
i.e., confidence_score < 0.75

Responsibility:
  Analyze WHY confidence is low and decide:
    A) ESCALATE   → which tier (Branch / Zone / Region / HO)
    B) HUMAN_AT_CURRENT_TIER → stay at current tier, assign human

  This agent is deterministic (no LLM call).
  Every decision is logged to agent_decisions for XAI + RBI audit trail.

Decision Rules (in priority order):
  Rule 1: Explicit higher-tier keywords in complaint text
          → Escalate to keyword-mapped tier

  Rule 2: RBI reportable + current_tier < 4
          → Escalate to Tier 4 (mandatory regulatory requirement)

  Rule 3: Authority gap — Agent 8 flagged authority_sufficient = False
          → Escalate to current_tier + 1

  Rule 4: Category-tier mismatch
          → Escalate to category's required minimum tier

  Rule 5: No signals above + confidence >= 0.80
          → HUMAN_AT_CURRENT_TIER (confidence gap is small, tier is fine)

  Rule 6: No signals above + confidence < 0.80
          → Escalate to current_tier + 1 (significant confidence gap)

Tier Map:
  Tier 1 → Branch Level
  Tier 2 → Zonal Office
  Tier 3 → Regional Office
  Tier 4 → Head Office / Nodal Officer
  Tier 5 → RBI Ombudsman (external — flagged only, not routed)

Output:
  decision          : "ESCALATE" | "HUMAN_AT_CURRENT_TIER"
  target_tier       : int (1-5) — only meaningful when decision == ESCALATE
  target_tier_label : str — human-readable tier name
  signals_detected  : list[str] — which rules fired
  reasoning         : str — full XAI audit trail
  rule_triggered    : str — highest-priority rule that decided outcome
  sla_hours         : int — SLA for assigned tier
  shadow_eligible   : bool — can shadow mode apply at this tier
"""

from datetime import datetime, timezone, timedelta
from app.db.supabase_client import get_supabase
from app.services.auto_responder import (
    SAFE_SENTIMENTS_FOR_AUTO,
    NEVER_AUTO_SEND_CATEGORIES,
    _simulate_send_to_customer,
    _save_auto_response_to_dataset,
)
from app.services.rbi.tat_rules import calculate_tat_deadline


# ── Constants ────────────────────────────────────────────────────────────────

SHADOW_OVERRIDE_WINDOW_HOURS = 1

CONFIDENCE_ESCALATION_THRESHOLD = 0.80

TIER_META = {
    1: {"label": "Branch Level",           "sla_hours": 24,  "shadow_eligible": True},
    2: {"label": "Zonal Office",           "sla_hours": 48,  "shadow_eligible": True},
    3: {"label": "Regional Office",        "sla_hours": 72,  "shadow_eligible": False},
    4: {"label": "Head Office / Nodal",    "sla_hours": 96,  "shadow_eligible": False},
    5: {"label": "RBI Ombudsman",          "sla_hours": 240, "shadow_eligible": False},
}

MAX_INTERNAL_TIER = 4   # Tier 5 is external (RBI), cannot be internally routed

# Rule 1: Keywords in complaint text that signal a specific tier
# Format: keyword → minimum tier required
ESCALATION_KEYWORDS = {
    # Tier 1 — Branch-level explicit mentions
    # (Useful when complaint starts below Tier 1 or pipeline needs to confirm minimum tier)
    "branch manager":            1,
    "branch head":               1,
    "branch officer":            1,
    "customer service officer":  1,
    "relationship manager":      1,
    "home branch":               1,
    "base branch":               1,
    "service branch":            1,
    "account opening form":      1,
    "counter staff":             1,
    "teller":                    1,

    # Tier 2 — Zonal keywords
    "zonal":                     2,
    "zone office":               2,
    "zonal manager":             2,
    "cluster head":              2,
    "zone head":                 2,
    "zonal head":                2,
    "zonal officer":             2,
    "area manager":              2,
    "area office":               2,
    "circle office":             2,
    "circle head":               2,
    "controlling office":        2,
    "lead bank":                 2,
    "lead district manager":     2,
    "field general manager":     2,
    "fgm":                       2,
    "divisional manager":        2,
    "divisional office":         2,
    "zonal grievance":           2,
    "zone grievance":            2,
    "cluster manager":           2,
    "territory manager":         2,

    # Tier 3 — Regional keywords  (DO NOT MODIFY)
    "regional":          3,
    "regional manager":  3,
    "regional office":   3,

    # Tier 4 — HO / Nodal keywords  (DO NOT MODIFY)
    "nodal officer":     4,
    "head office":       4,
    "grievance officer": 4,
    "chief manager":     4,
    "rbi":               4,
    "ombudsman":         4,
    "banking ombudsman": 5,
    "consumer forum":    4,
    "legal notice":      4,
    "court":             4,
    "fir":               4,
    "police complaint":  4,
}

# Rule 4: Category → minimum tier required
# Categories that inherently need higher authority
CATEGORY_MINIMUM_TIER = {
    # ── Tier 1 — Branch can handle ───────────────────────────────────────────
    "General Banking":              1,
    "KYC":                         1,
    "Debit Card":                  1,
    # Digital payments — branch can initiate reversal / lodge claim
    "ATM":                         1,
    "Net Banking":                 1,
    "Mobile Banking":              1,
    "Internet Banking":            1,
    "UPI":                         1,
    "NEFT":                        1,
    "RTGS":                        1,
    "IMPS":                        1,
    # Account & instrument level
    "Cheque":                      1,
    "Savings Account":             1,
    "Current Account":             1,
    "Account Statement":           1,
    "Passbook":                    1,
    "Fixed Deposit":               1,
    "Recurring Deposit":           1,
    "Locker":                      1,
    "Nomination":                  1,
    "Account Closure":             1,
    "Account Opening":             1,
    "Pension Account":             1,
    "Senior Citizen Account":      1,
    "Jan Dhan Account":            1,
    # Card & OTP
    "Credit Card Billing":         1,   # billing queries (disputes → Tier 2)
    "OTP Issue":                   1,
    "Card Delivery":               1,

    # ── Tier 2 — Zonal minimum (loan grievances, complex products) ───────────
    "Home Loan":                   2,
    "Personal Loan":               2,
    "Business Loan":               2,
    "Insurance":                   2,
    "Vehicle Loan":                2,
    "Two Wheeler Loan":            2,
    "Education Loan":              2,
    "Agriculture Loan":            2,
    "Crop Loan":                   2,
    "Kisan Credit Card":           2,
    "Loan Against Property":       2,
    "Gold Loan":                   2,
    "Microfinance":                2,
    "Overdraft":                   2,
    "Cash Credit":                 2,
    "Term Loan":                   2,
    "Credit Card":                 2,   # fraud / dispute level (not billing)
    "NRI Account":                 2,
    "Priority Banking":            2,
    "Wealth Management":           2,
    "Mutual Fund":                 2,
    "Demat Account":               2,
    "Trading Account":             2,

    # ── Tier 3 — Regional minimum  (DO NOT MODIFY) ───────────────────────────
    "CREDIT_BUREAU_MISREPORTING":  3,
    "MIS_SELLING_OF_PRODUCTS":     3,
    "UNSOLICITED_CARD_ISSUANCE":   3,

    # ── Tier 4 — HO / Nodal mandatory  (DO NOT MODIFY) ──────────────────────
    "UNAUTHORIZED_TRANSACTION_FRAUD":  4,
    "RECOVERY_AGENT_HARASSMENT":       4,
    "DELAY_IN_PROPERTY_DOC_RELEASE":   4,
}


# ── Main Agent Function ───────────────────────────────────────────────────────

def analyze_escalation(
    # Complaint context
    complaint_id: str,
    complaint_text: str,           # masked_text from Agent 1
    category: str,                 # from Agent 3 (Classification)
    compliance_category: str,      # from Agent 5 (Compliance)
    is_rbi_reportable: bool,       # from Agent 5
    sentiment: str,                # from Agent 4
    severity: int,                 # from Agent 6
    # Pipeline signals
    confidence_score: float,       # from Agent 8
    grounding_score: float,        # from Agent 9
    authority_sufficient: bool,    # from Agent 8 — did resolution agent have authority?
    draft_response: str,           # from Agent 8
    # Current routing context
    current_tier: int,             # 1-4, where complaint currently is
    # Pass-through from Agent 10
    risk_score: float,
    risk_breakdown: dict,
) -> dict:
    """
    Analyze escalation signals and decide tier assignment.

    Returns full decision dict for pipeline state + agent_decisions logging.
    """
    signals_detected = []
    reasoning_steps  = []
    keyword_tier     = None
    category_tier    = None

    # ── Rule 1: Keyword scan ─────────────────────────────────────────────────
    complaint_lower = complaint_text.lower()
    matched_keywords = []

    for keyword, required_tier in ESCALATION_KEYWORDS.items():
        if keyword in complaint_lower:
            matched_keywords.append((keyword, required_tier))

    if matched_keywords:
        keyword_tier = max(t for _, t in matched_keywords)
        matched_str  = ", ".join(f'"{k}"→T{t}' for k, t in matched_keywords)
        signals_detected.append(f"KEYWORD_MATCH: {matched_str}")
        reasoning_steps.append(
            f"Rule 1 — Keyword match: [{matched_str}]. "
            f"Highest tier implied: Tier {keyword_tier}."
        )
    else:
        reasoning_steps.append("Rule 1 — No escalation keywords found in complaint text.")

    # ── Rule 2: RBI reportable + tier < 4 ───────────────────────────────────
    rbi_escalation = False
    if is_rbi_reportable and current_tier < 4:
        rbi_escalation = True
        signals_detected.append(
            f"RBI_MANDATORY: is_rbi_reportable=True, current_tier={current_tier} < 4"
        )
        reasoning_steps.append(
            f"Rule 2 — RBI reportable complaint at Tier {current_tier}. "
            f"Mandatory escalation to Tier 4 (Head Office / Nodal Officer)."
        )
    else:
        reasoning_steps.append(
            f"Rule 2 — RBI check: reportable={is_rbi_reportable}, "
            f"current_tier={current_tier}. No mandatory escalation."
        )

    # ── Rule 3: Authority gap ────────────────────────────────────────────────
    authority_gap = False
    if not authority_sufficient:
        authority_gap = True
        signals_detected.append(
            f"AUTHORITY_GAP: Agent 8 flagged authority_sufficient=False "
            f"at current_tier={current_tier}"
        )
        reasoning_steps.append(
            f"Rule 3 — Authority gap detected. "
            f"Agent 8 could not resolve at Tier {current_tier}. "
            f"Escalating to Tier {min(current_tier + 1, MAX_INTERNAL_TIER)}."
        )
    else:
        reasoning_steps.append(
            "Rule 3 — Authority check: Agent 8 had sufficient authority. No gap."
        )

    # ── Rule 4: Category-tier mismatch ──────────────────────────────────────
    # Check both category (from Agent 3) and compliance_category (from Agent 5)
    cat_min = CATEGORY_MINIMUM_TIER.get(category, 1)
    comp_min = CATEGORY_MINIMUM_TIER.get(compliance_category, 1)
    category_tier = max(cat_min, comp_min)

    if category_tier > current_tier:
        signals_detected.append(
            f"CATEGORY_TIER_MISMATCH: category='{category}' / "
            f"compliance='{compliance_category}' requires min Tier {category_tier}, "
            f"but current_tier={current_tier}"
        )
        reasoning_steps.append(
            f"Rule 4 — Category mismatch: '{category}' / '{compliance_category}' "
            f"requires minimum Tier {category_tier}. "
            f"Current tier {current_tier} is insufficient."
        )
    else:
        reasoning_steps.append(
            f"Rule 4 — Category tier check: '{category}' min={category_tier}, "
            f"current_tier={current_tier}. No mismatch."
        )
        category_tier = None  # No mismatch, don't use this for escalation

    # ── Decision Logic ───────────────────────────────────────────────────────

    # If ANY of Rules 1-4 fired → ESCALATE
    if keyword_tier or rbi_escalation or authority_gap or category_tier:

        # Calculate target tier — highest of all signals
        candidate_tiers = []

        if keyword_tier:
            candidate_tiers.append(keyword_tier)

        if rbi_escalation:
            candidate_tiers.append(4)  # RBI → always Tier 4 minimum

        if authority_gap:
            candidate_tiers.append(min(current_tier + 1, MAX_INTERNAL_TIER))

        if category_tier:
            candidate_tiers.append(category_tier)

        target_tier  = min(max(candidate_tiers), MAX_INTERNAL_TIER)
        rule_triggered = _highest_priority_rule(
            keyword_tier, rbi_escalation, authority_gap, category_tier
        )

        # Tier 5 special case — flag only, cannot internally route
        if keyword_tier == 5:
            signals_detected.append(
                "OMBUDSMAN_FLAG: Complaint mentions RBI Ombudsman — "
                "flagged for Nodal Officer awareness. Routing to Tier 4."
            )
            target_tier = 4  # Internal max

        tier_info  = TIER_META[target_tier]
        tat        = calculate_tat_deadline(compliance_category if is_rbi_reportable else "NOT_APPLICABLE")
        sla_deadline = tat["tat_deadline_iso"] if is_rbi_reportable else None

        reasoning = (
            f"ESCALATION DECISION: ESCALATE → Tier {target_tier} "
            f"({tier_info['label']})\n"
            f"Complaint ID: {complaint_id}\n"
            f"Confidence: {confidence_score:.1%} (below 95% gate)\n"
            f"Current tier: {current_tier} → Target tier: {target_tier}\n"
            f"Primary rule: {rule_triggered}\n"
            f"Signals detected ({len(signals_detected)}):\n"
            + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(signals_detected))
            + f"\n\nReasoning steps:\n"
            + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(reasoning_steps))
            + f"\n\nRisk score (from Agent 10): {risk_score}"
        )

        return {
            "decision":           "ESCALATE",
            "target_tier":        target_tier,
            "target_tier_label":  tier_info["label"],
            "signals_detected":   signals_detected,
            "rule_triggered":     rule_triggered,
            "reasoning":          reasoning,
            "sla_hours":          tier_info["sla_hours"],
            "sla_deadline":       sla_deadline,
            "shadow_eligible":    tier_info["shadow_eligible"],
            "confidence_score":   confidence_score,
            "risk_score":         risk_score,
            "risk_breakdown":     risk_breakdown,
        }

    # ── Rules 5 & 6: No escalation signals ──────────────────────────────────

    # Rule 5: confidence >= 0.80 → human at current tier
    if confidence_score >= CONFIDENCE_ESCALATION_THRESHOLD:
        tier_info    = TIER_META[current_tier]
        tat          = calculate_tat_deadline(compliance_category if is_rbi_reportable else "NOT_APPLICABLE")
        sla_deadline = tat["tat_deadline_iso"] if is_rbi_reportable else None

        reasoning_steps.append(
            f"Rule 5 — Confidence {confidence_score:.1%} >= {CONFIDENCE_ESCALATION_THRESHOLD:.0%}. "
            f"No escalation signals. Assigning human at current Tier {current_tier}."
        )

        reasoning = (
            f"ESCALATION DECISION: HUMAN_AT_CURRENT_TIER (Tier {current_tier} — "
            f"{tier_info['label']})\n"
            f"Complaint ID: {complaint_id}\n"
            f"Confidence: {confidence_score:.1%} — in 80-95% range, no escalation signals\n"
            f"No signals detected. Tier {current_tier} is appropriate.\n"
            f"Reasoning steps:\n"
            + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(reasoning_steps))
        )

        return {
            "decision":           "HUMAN_AT_CURRENT_TIER",
            "target_tier":        current_tier,
            "target_tier_label":  tier_info["label"],
            "signals_detected":   [],
            "rule_triggered":     "Rule 5 — Confidence 80-95%, no signals",
            "reasoning":          reasoning,
            "sla_hours":          tier_info["sla_hours"],
            "sla_deadline":       sla_deadline,
            "shadow_eligible":    tier_info["shadow_eligible"],
            "confidence_score":   confidence_score,
            "risk_score":         risk_score,
            "risk_breakdown":     risk_breakdown,
        }

    # Rule 6: confidence < 0.80 → escalate to tier+1
    target_tier = min(current_tier + 1, MAX_INTERNAL_TIER)
    tier_info   = TIER_META[target_tier]
    tat         = calculate_tat_deadline(compliance_category if is_rbi_reportable else "NOT_APPLICABLE")
    sla_deadline = tat["tat_deadline_iso"] if is_rbi_reportable else None

    signals_detected.append(
        f"LOW_CONFIDENCE: {confidence_score:.1%} < {CONFIDENCE_ESCALATION_THRESHOLD:.0%} "
        f"with no other signals — significant confidence gap"
    )
    reasoning_steps.append(
        f"Rule 6 — Confidence {confidence_score:.1%} < {CONFIDENCE_ESCALATION_THRESHOLD:.0%}. "
        f"Significant confidence gap. Escalating from Tier {current_tier} → Tier {target_tier}."
    )

    reasoning = (
        f"ESCALATION DECISION: ESCALATE → Tier {target_tier} "
        f"({tier_info['label']})\n"
        f"Complaint ID: {complaint_id}\n"
        f"Confidence: {confidence_score:.1%} — below 80% with no other signals\n"
        f"Rule 6 triggered: significant confidence gap → tier+1\n"
        f"Current tier: {current_tier} → Target tier: {target_tier}\n"
        f"Reasoning steps:\n"
        + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(reasoning_steps))
        + f"\n\nRisk score (from Agent 10): {risk_score}"
    )

    return {
        "decision":           "ESCALATE",
        "target_tier":        target_tier,
        "target_tier_label":  tier_info["label"],
        "signals_detected":   signals_detected,
        "rule_triggered":     "Rule 6 — Confidence < 80%, no signals",
        "reasoning":          reasoning,
        "sla_hours":          tier_info["sla_hours"],
        "sla_deadline":       sla_deadline,
        "shadow_eligible":    tier_info["shadow_eligible"],
        "confidence_score":   confidence_score,
        "risk_score":         risk_score,
        "risk_breakdown":     risk_breakdown,
    }


# ── Shadow Mode (moved from auto_responder.py) ───────────────────────────────

def execute_shadow_mode(
    complaint_id: str,
    customer_id: str,
    channel: str,
    draft_response: str,
    confidence_score: float,
    target_tier: int,
) -> dict:
    """
    Shadow mode — auto-send to customer + notify human agent at target_tier.

    Conditions for shadow eligibility:
      - target_tier in {1, 2} (shadow_eligible = True)
      - confidence >= 0.80 (below this, too risky for shadow)
      - Not in NEVER_AUTO_SEND_CATEGORIES (checked by caller)

    Called by pipeline executor after Agent 10.5 returns
    decision == HUMAN_AT_CURRENT_TIER or ESCALATE with shadow_eligible = True
    and confidence >= 0.80.
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    _simulate_send_to_customer(
        customer_id=customer_id,
        channel=channel,
        draft_response=draft_response,
        send_type="SHADOW_AUTO",
        complaint_id=complaint_id,
    )

    override_deadline = now + timedelta(hours=SHADOW_OVERRIDE_WINDOW_HOURS)

    _notify_human_agent_shadow(
        complaint_id=complaint_id,
        draft_response=draft_response,
        confidence_score=confidence_score,
        override_deadline=override_deadline,
        target_tier=target_tier,
    )

    supabase.table("complaints").update({
        "status":                   "shadow_sent",
        "pipeline_status":          "complete",
        "response_tier":            "shadow",
        "auto_sent_at":             now.isoformat(),
        "shadow_override_deadline": override_deadline.isoformat(),
        "shadow_overridden":        False,
        "assigned_tier":            target_tier,
    }).eq("complaint_id", complaint_id).execute()

    return {
        "action_taken":         "shadow_auto_sent",
        "sent_to_customer":     True,
        "human_notified":       True,
        "override_deadline":    override_deadline.isoformat(),
        "override_window_hours": SHADOW_OVERRIDE_WINDOW_HOURS,
        "status":               "shadow_sent",
        "assigned_tier":        target_tier,
        "message": (
            f"Response shadow-sent to customer. "
            f"Tier {target_tier} agent has {SHADOW_OVERRIDE_WINDOW_HOURS}hr to override."
        ),
    }


def execute_shadow_override(
    complaint_id: str,
    agent_id: str,
    corrected_response: str,
    override_reason: str,
) -> dict:
    """
    Shadow mode mein human agent override karta hai.
    Moved here from auto_responder.py.

    Steps:
      1. Validate complaint is in shadow_sent status
      2. Check override window is still open
      3. Send corrected response to customer
      4. Update DB
      5. Save negative signal to fine_tune_dataset
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, status, shadow_override_deadline, "
            "shadow_overridden, customer_id, channel, draft_response"
        )
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    complaint = result.data[0]

    if complaint.get("status") != "shadow_sent":
        raise ValueError(
            f"Complaint is not in shadow mode. "
            f"Current status: {complaint.get('status')}"
        )

    if complaint.get("shadow_overridden"):
        raise ValueError("Shadow override already applied for this complaint")

    deadline_str = complaint.get("shadow_override_deadline")
    if deadline_str:
        deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        if now > deadline:
            raise ValueError(
                f"Override window expired at {deadline.isoformat()}. "
                f"Cannot override after {SHADOW_OVERRIDE_WINDOW_HOURS} hours."
            )

    _simulate_send_to_customer(
        customer_id=complaint.get("customer_id", ""),
        channel=complaint.get("channel", "web"),
        draft_response=corrected_response,
        send_type="SHADOW_OVERRIDE_CORRECTION",
        complaint_id=complaint_id,
    )

    supabase.table("complaints").update({
        "status":           "override_closed",
        "shadow_overridden": True,
    }).eq("complaint_id", complaint_id).execute()

    supabase.table("agent_feedback").insert({
        "complaint_id":    complaint_id,
        "agent_id":        agent_id,
        "action":          "edit",
        "original_draft":  complaint.get("draft_response", ""),
        "final_response":  corrected_response,
        "agent_score":     0.5,
    }).execute()

    # Auto-sent draft was wrong → negative signal in dataset
    _save_auto_response_to_dataset(
        complaint_id=complaint_id,
        draft_response=complaint.get("draft_response", ""),
        tier="shadow_overridden",
        agent_score=0.0,
    )

    return {
        "complaint_id":             complaint_id,
        "override_applied":         True,
        "corrected_response_sent":  True,
        "agent_id":                 agent_id,
        "override_reason":          override_reason,
        "message":                  "Override applied. Corrected response sent to customer.",
    }


# ── Private Helpers ───────────────────────────────────────────────────────────

def _highest_priority_rule(
    keyword_tier,
    rbi_escalation: bool,
    authority_gap: bool,
    category_tier,
) -> str:
    """
    Rules priority order:
      Rule 2 (RBI) > Rule 1 (Keyword) > Rule 4 (Category) > Rule 3 (Authority)
    RBI compliance always takes highest priority for audit purposes.
    """
    if rbi_escalation:
        return "Rule 2 — RBI mandatory escalation"
    if keyword_tier:
        return f"Rule 1 — Keyword match (tier {keyword_tier})"
    if category_tier:
        return f"Rule 4 — Category-tier mismatch (min tier {category_tier})"
    if authority_gap:
        return "Rule 3 — Authority gap (Agent 8 flagged)"
    return "Unknown"


def _notify_human_agent_shadow(
    complaint_id: str,
    draft_response: str,
    confidence_score: float,
    override_deadline: datetime,
    target_tier: int,
) -> None:
    """
    Shadow mode — human agent ko notify karo at target_tier.
    Production: Email / Slack / Dashboard push notification.
    """
    tier_label = TIER_META.get(target_tier, {}).get("label", f"Tier {target_tier}")
    print(f"\n{'='*60}")
    print(f"[SHADOW NOTIFY] Complaint      : {complaint_id}")
    print(f"[SHADOW NOTIFY] Assigned Tier  : {target_tier} ({tier_label})")
    print(f"[SHADOW NOTIFY] Confidence     : {confidence_score:.1%}")
    print(f"[SHADOW NOTIFY] Auto-sent to customer.")
    print(f"[SHADOW NOTIFY] Override window: until {override_deadline.strftime('%H:%M UTC')}")
    print(f"[SHADOW NOTIFY] Override API   : POST /api/v1/complaints/{complaint_id}/shadow-override")
    print(f"{'='*60}\n")