"""
Tier Context Manager

Assembles all tier-specific context needed by partial_pipeline_runner:
  - Tier name / authority label
  - Contact info for this tier
  - Previous tier attempts (for Agent 8 prompt)
  - SLA hours + shadow eligibility
"""

from app.services.agents.esclation_analyzer import TIER_META


_TIER_CONTACT_INFO: dict[int, str] = {
    1: "Branch Manager, branch helpdesk: 1800-XXX-XXXX (toll-free)",
    2: "Zonal Office, Zonal Manager — contact via branch referral",
    3: "Regional Nodal Officer, Regional Office grievance cell",
    4: "Head Office Grievance Cell, Nodal Officer: nodal@bank.com | 1800-XXX-1234",
    5: "RBI Banking Ombudsman: cms.rbi.org.in | Toll Free: 14448",
}


def get_tier_context(
    complaint_id: str,
    tier_level: int,
    from_tier: int = None,
) -> dict:
    """
    Returns enriched tier context dict consumed by partial_pipeline_runner.
    """
    tier_info = TIER_META.get(
        tier_level,
        {"label": f"Tier {tier_level}", "sla_hours": 72, "shadow_eligible": False},
    )

    tier_contact_info = _TIER_CONTACT_INFO.get(
        tier_level, f"Tier {tier_level} escalation team"
    )

    previous_attempts_prompt = ""
    if from_tier is not None and complaint_id:
        from app.services.previous_tier_context import format_previous_attempts_for_prompt
        previous_attempts_prompt = format_previous_attempts_for_prompt(
            complaint_id, from_tier, tier_level
        )

    return {
        "current_tier": tier_level,
        "tier_name": tier_info["label"],
        "tier_contact_info": tier_contact_info,
        "previous_attempts_prompt": previous_attempts_prompt,
        "sla_hours": tier_info["sla_hours"],
        "shadow_eligible": tier_info["shadow_eligible"],
    }
