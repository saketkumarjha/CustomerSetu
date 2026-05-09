from app.core.config import get_settings


def validate_transition(from_tier: int, to_tier: int, reason: str = "") -> dict:
    """
    Validate that a tier transition is legitimate.

    Hard blocks:
      - Cannot de-escalate (to_tier <= from_tier)
      - Cannot exceed max tier

    Soft warnings (logged but allowed):
      - Jump > 2 tiers at once (suspicious without keyword signals)
    """
    settings = get_settings()
    warnings = []

    if to_tier <= from_tier:
        return {
            "is_valid": False,
            "reason": f"Cannot de-escalate from Tier {from_tier} to Tier {to_tier}.",
            "warnings": [],
        }

    if to_tier > settings.max_escalation_tier:
        return {
            "is_valid": False,
            "reason": (
                f"Target tier {to_tier} exceeds max allowed tier "
                f"{settings.max_escalation_tier}."
            ),
            "warnings": [],
        }

    jump = to_tier - from_tier
    if jump > 2:
        warnings.append(
            f"Large tier jump: Tier {from_tier} → Tier {to_tier} ({jump} levels). "
            "Verify escalation signals justify this skip."
        )

    return {"is_valid": True, "reason": "Transition valid.", "warnings": warnings}
