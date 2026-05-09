"""
Escalation Timeline Calculator

Calculates "auto-escalates in X hours" message included in every auto-response.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

# Tier metadata — mirrors TIER_META in esclation_analyzer.py
# (Duplicated here to avoid circular imports)
_TIER_META = {
    1: {"label": "Branch Level",         "sla_hours": 24},
    2: {"label": "Zonal Office",         "sla_hours": 48},
    3: {"label": "Regional Office",      "sla_hours": 72},
    4: {"label": "Head Office / Nodal",  "sla_hours": 96},
    5: {"label": "RBI Ombudsman",        "sla_hours": 240},
}

MAX_INTERNAL_TIER = 4
# 2-hour buffer before SLA deadline triggers escalation notification
_ESCALATION_BUFFER_HOURS = 2


def calculate_escalation_info(
    tier_level: int,
    sla_deadline: Optional[str] = None,
) -> dict:
    """
    Calculate escalation timeline for inclusion in auto-response message.

    Args:
        tier_level:   Current tier where complaint is resolved (1–4).
        sla_deadline: ISO datetime string from RBI TAT calculator (optional).
                      If absent, derived from tier SLA hours.

    Returns dict with:
        message:                   Human-readable escalation sentence.
        next_tier:                 int | None — tier that gets the complaint next.
        next_tier_name:            str — label for next tier.
        deadline_formatted:        Human-readable SLA deadline.
        escalation_trigger_formatted: Time when auto-escalation fires.
        escalation_deadline_iso:   ISO string for escalation trigger.
        sla_deadline_iso:          ISO string for full SLA deadline.
        is_final_tier:             True when tier_level >= MAX_INTERNAL_TIER.
    """
    tier_level = max(1, min(tier_level, 5))
    tier_info = _TIER_META.get(tier_level, {"label": f"Tier {tier_level}", "sla_hours": 24})

    # Derive SLA deadline datetime
    if sla_deadline:
        try:
            deadline_dt = datetime.fromisoformat(sla_deadline.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            deadline_dt = datetime.now(timezone.utc) + timedelta(
                hours=tier_info["sla_hours"]
            )
    else:
        deadline_dt = datetime.now(timezone.utc) + timedelta(hours=tier_info["sla_hours"])

    escalation_trigger_dt = deadline_dt - timedelta(hours=_ESCALATION_BUFFER_HOURS)

    deadline_formatted = deadline_dt.strftime("%d %B %Y, %I:%M %p UTC")
    escalation_formatted = escalation_trigger_dt.strftime("%d %B %Y, %I:%M %p UTC")

    is_final_tier = tier_level >= MAX_INTERNAL_TIER

    next_tier = None if is_final_tier else tier_level + 1
    if next_tier:
        next_tier_name = _TIER_META.get(next_tier, {}).get("label", f"Tier {next_tier}")
    else:
        next_tier_name = "RBI Banking Ombudsman (external)"

    if is_final_tier:
        message = (
            "Your complaint has been addressed at the highest internal resolution level "
            "(Head Office / Nodal Officer). If you remain unsatisfied, you may approach "
            "the RBI Banking Ombudsman at https://cms.rbi.org.in."
        )
    else:
        message = (
            f"If your complaint is not resolved by {escalation_formatted}, "
            f"it will automatically escalate to {next_tier_name}."
        )

    return {
        "message": message,
        "next_tier": next_tier,
        "next_tier_name": next_tier_name,
        "deadline_formatted": deadline_formatted,
        "escalation_trigger_formatted": escalation_formatted,
        "escalation_deadline_iso": escalation_trigger_dt.isoformat(),
        "sla_deadline_iso": deadline_dt.isoformat(),
        "is_final_tier": is_final_tier,
    }
