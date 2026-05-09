"""
Previous Tier Context Builder

Queries complaint_escalation_history to build a summary of what every
previous tier attempted and why it failed.  This is fed into Agent 8
(Resolution Generator) so the new tier doesn't repeat failed approaches.
"""

import json
from app.db.supabase_client import get_supabase


def build_previous_tier_context(complaint_id: str) -> dict:
    supabase = get_supabase()

    result = (
        supabase.table("complaint_escalation_history")
        .select(
            "from_tier, to_tier, tier_response_text, "
            "confidence_before, escalation_decision_reasoning, escalated_at"
        )
        .eq("complaint_id", complaint_id)
        .order("escalated_at", desc=False)
        .execute()
    )

    attempts: dict = {}
    previous_lines: list[str] = []

    for row in result.data or []:
        tier = row.get("from_tier")
        response_text = row.get("tier_response_text", "") or ""
        confidence = row.get("confidence_before") or 0.0
        reason = row.get("escalation_decision_reasoning", "") or ""

        if tier is not None:
            attempts[f"tier_{tier}_attempt"] = {
                "response": response_text,
                "confidence": confidence,
                "why_failed": reason,
            }
            if response_text:
                previous_lines.append(
                    f"Tier {tier} attempt (confidence {confidence:.0%}): "
                    f"{response_text[:200].strip()} "
                    f"[escalated because: {reason[:120].strip()}]"
                )

    return {
        "attempts": attempts,
        "summary": "\n\n".join(previous_lines),
        "attempt_count": len(attempts),
    }


def format_previous_attempts_for_prompt(
    complaint_id: str,
    from_tier: int,
    to_tier: int,
) -> str:
    """
    Return the escalation context string injected into Agent 8's system prompt.
    Returns empty string if no previous attempts exist.
    """
    ctx = build_previous_tier_context(complaint_id)

    if not ctx["summary"]:
        return ""

    return (
        f"This complaint has been escalated from Tier {from_tier} to Tier {to_tier}.\n\n"
        f"PREVIOUS TIER ATTEMPTS (do NOT repeat these approaches):\n"
        f"{ctx['summary']}\n\n"
        f"You are now at Tier {to_tier}. Provide NEW, actionable information that "
        f"only your tier's authority and resources can offer."
    )
