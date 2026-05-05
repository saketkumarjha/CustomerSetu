"""
RBI TAT (Turnaround Time) Rules

Maps each RBI category to:
  - acknowledgement_hours: When customer must be acknowledged
  - resolution_hours:      When complaint must be resolved
  - penalty_per_day:       Auto-penalty if TAT breached (Rs/day)
  - penalty_description:   What triggers the penalty

These are based on actual RBI circulars.
For POC: we assign the TAT deadline at the time of routing.
For Production: a background job checks approaching breaches and escalates.
"""

from datetime import datetime, timedelta, timezone
from app.services.rbi.categories import RBICategory


TAT_RULES = {
    RBICategory.UNAUTHORIZED_TRANSACTION_FRAUD: {
        "acknowledgement_hours": 24,
        "resolution_hours": 240,      # 10 working days
        "penalty_per_day": 0,         # liability framework applies instead
        "penalty_description": (
            "RBI Limiting Liability Circular — provisional credit mandatory "
            "within 10 working days if customer not at fault"
        ),
        "sla_label": "10 working days (RBI Limiting Liability)",
    },
    RBICategory.FAILED_TRANSACTION_TAT_BREACH: {
        "acknowledgement_hours": 24,
        "resolution_hours": 120,      # 5 working days
        "penalty_per_day": 100,       # Rs 100/day after TAT breach
        "penalty_description": "RBI TAT Circular — Rs 100/day auto-penalty after 5 working days",
        "sla_label": "5 working days (₹100/day penalty after breach)",
    },
    RBICategory.UPI_BBPS_SETTLEMENT_ISSUE: {
        "acknowledgement_hours": 24,
        "resolution_hours": 24,       # T+1 day
        "penalty_per_day": 100,
        "penalty_description": "NPCI guidelines — auto-reversal within T+1 day",
        "sla_label": "T+1 day",
    },
    RBICategory.RECOVERY_AGENT_HARASSMENT: {
        "acknowledgement_hours": 4,   # immediate
        "resolution_hours": 24,
        "penalty_per_day": 0,
        "penalty_description": "RBI Fair Practices Code — immediate escalation to nodal officer",
        "sla_label": "24 hours (immediate escalation)",
    },
    RBICategory.DELAY_IN_PROPERTY_DOC_RELEASE: {
        "acknowledgement_hours": 24,
        "resolution_hours": 720,      # 30 days
        "penalty_per_day": 5000,      # Rs 5,000/day after 30 days
        "penalty_description": "RBI Responsible Lending Conduct 2023 — Rs 5,000/day after 30 days",
        "sla_label": "30 days (₹5,000/day penalty after breach)",
    },
    RBICategory.DELAY_IN_CARD_CLOSURE: {
        "acknowledgement_hours": 24,
        "resolution_hours": 168,      # 7 working days
        "penalty_per_day": 500,       # Rs 500/day
        "penalty_description": "RBI Master Direction on Credit Cards — Rs 500/day after 7 working days",
        "sla_label": "7 working days (₹500/day penalty after breach)",
    },
    RBICategory.UNSOLICITED_CARD_ISSUANCE: {
        "acknowledgement_hours": 24,
        "resolution_hours": 120,
        "penalty_per_day": 0,
        "penalty_description": "RBI Master Direction — billed amount reversed + 100% penalty",
        "sla_label": "5 working days",
    },
    RBICategory.CREDIT_BUREAU_MISREPORTING: {
        "acknowledgement_hours": 24,
        "resolution_hours": 720,      # 30 days
        "penalty_per_day": 0,
        "penalty_description": "CIC Act — update credit report within 30 days of closure",
        "sla_label": "30 days",
    },
    RBICategory.KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE: {
        "acknowledgement_hours": 24,
        "resolution_hours": 72,
        "penalty_per_day": 0,
        "penalty_description": "RBI KYC Master Direction — prior notice mandatory",
        "sla_label": "72 hours",
    },
}

# Default TAT for non-RBI categories
DEFAULT_TAT = {
    "acknowledgement_hours": 72,  # 3 working days
    "resolution_hours": 720,      # 30 days
    "penalty_per_day": 0,
    "penalty_description": "Standard complaint resolution — 30 days",
    "sla_label": "30 days",
}


def get_tat_for_category(rbi_category: str) -> dict:
    """Get TAT rules for a given RBI category string."""
    try:
        cat_enum = RBICategory(rbi_category)
        return TAT_RULES.get(cat_enum, DEFAULT_TAT)
    except ValueError:
        return DEFAULT_TAT


def calculate_tat_deadline(rbi_category: str) -> dict:
    """
    Calculate the actual TAT deadline datetime for a complaint.

    Returns dict with:
        tat_deadline_iso:    ISO datetime string of when this must be resolved
        sla_hours:           Total hours allowed
        penalty_per_day:     Auto-penalty amount if breached
        sla_label:           Human-readable SLA description
        acknowledgement_by:  ISO datetime of acknowledgement deadline
    """
    now = datetime.now(timezone.utc)
    tat = get_tat_for_category(rbi_category)

    tat_deadline = now + timedelta(hours=tat["resolution_hours"])
    acknowledgement_deadline = now + timedelta(hours=tat["acknowledgement_hours"])

    return {
        "tat_deadline_iso": tat_deadline.isoformat(),
        "acknowledgement_by_iso": acknowledgement_deadline.isoformat(),
        "sla_hours": tat["resolution_hours"],
        "penalty_per_day": tat["penalty_per_day"],
        "penalty_description": tat["penalty_description"],
        "sla_label": tat["sla_label"],
    }