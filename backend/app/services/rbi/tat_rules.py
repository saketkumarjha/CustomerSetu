"""
RBI TAT (Turnaround Time) Rules

Maps each RBI category to:
  - acknowledgement_hours: When customer must be acknowledged
  - resolution_hours:      When complaint must be resolved
  - penalty_per_day:       Auto-penalty if TAT breached (Rs/day)
  - penalty_description:   What triggers the penalty

Resolution window is standardized to 30 calendar days (720 hours) for all categories,
aligned with common RBI complaint-handling / grievance redressal timelines (POC default).

For POC: we assign the TAT deadline at the time of routing.
For Production: a background job checks approaching breaches and escalates.
"""

from datetime import datetime, timedelta, timezone
from app.services.rbi.categories import RBICategory

# 30 calendar days × 24 hours — uniform resolution SLA (RBI-aligned grievance window)
RESOLUTION_30_DAYS_HOURS = 720

TAT_RULES = {
    RBICategory.UNAUTHORIZED_TRANSACTION_FRAUD: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 0,
        "penalty_description": (
            "RBI framework — resolution within 30 calendar days; "
            "limiting-liability / provisional credit rules apply as per circular"
        ),
        "sla_label": "30 calendar days (RBI complaint resolution)",
    },
    RBICategory.FAILED_TRANSACTION_TAT_BREACH: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 100,
        "penalty_description": "RBI TAT — ₹100/day auto-penalty after resolution timeline breach",
        "sla_label": "30 calendar days (₹100/day after breach)",
    },
    RBICategory.UPI_BBPS_SETTLEMENT_ISSUE: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 100,
        "penalty_description": "NPCI / settlement rules — penalties after resolution timeline breach where applicable",
        "sla_label": "30 calendar days",
    },
    RBICategory.RECOVERY_AGENT_HARASSMENT: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 0,
        "penalty_description": "RBI Fair Practices Code — escalate per policy within resolution window",
        "sla_label": "30 calendar days",
    },
    RBICategory.DELAY_IN_PROPERTY_DOC_RELEASE: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 5000,
        "penalty_description": "RBI Responsible Lending Conduct — ₹5,000/day after resolution timeline breach",
        "sla_label": "30 calendar days (₹5,000/day penalty after breach)",
    },
    RBICategory.DELAY_IN_CARD_CLOSURE: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 500,
        "penalty_description": "RBI Master Direction on Credit Cards — ₹500/day after resolution timeline breach",
        "sla_label": "30 calendar days (₹500/day penalty after breach)",
    },
    RBICategory.UNSOLICITED_CARD_ISSUANCE: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 0,
        "penalty_description": "RBI Master Direction — resolution within 30 calendar days",
        "sla_label": "30 calendar days",
    },
    RBICategory.CREDIT_BUREAU_MISREPORTING: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 0,
        "penalty_description": "CIC Act — update credit report within timeline after closure",
        "sla_label": "30 calendar days",
    },
    RBICategory.KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE: {
        "acknowledgement_hours": 24,
        "resolution_hours": RESOLUTION_30_DAYS_HOURS,
        "penalty_per_day": 0,
        "penalty_description": "RBI KYC Master Direction — resolve within 30 calendar days",
        "sla_label": "30 calendar days",
    },
}

# Default TAT for non-RBI or unknown categories
DEFAULT_TAT = {
    "acknowledgement_hours": 24,
    "resolution_hours": RESOLUTION_30_DAYS_HOURS,
    "penalty_per_day": 0,
    "penalty_description": "Standard complaint resolution — 30 calendar days (RBI-aligned)",
    "sla_label": "30 calendar days",
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
