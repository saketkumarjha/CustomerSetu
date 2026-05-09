from datetime import datetime, timezone
from typing import Optional


def detect_loop(
    complaint_id: str,
    escalation_path: list,
    last_escalation_at: Optional[str] = None,
    escalation_count: int = 0,
) -> dict:
    """
    Detect abnormal escalation patterns that indicate logic bugs.

    Patterns caught:
      - Circular : same tier appears twice in the path (0→1→2→1)
      - Rapid    : >= 3 escalations completed in < 60 seconds
    """
    loop_detected = False
    loop_reason = None

    # Circular: duplicate tier in path
    if len(escalation_path) != len(set(escalation_path)):
        loop_detected = True
        loop_reason = f"CIRCULAR: path contains repeated tier — {escalation_path}"

    # Rapid fire: many escalations within 60 s
    if not loop_detected and last_escalation_at and escalation_count >= 3:
        try:
            last_at = datetime.fromisoformat(last_escalation_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - last_at).total_seconds()
            if elapsed < 60:
                loop_detected = True
                loop_reason = (
                    f"RAPID: {escalation_count} escalations, "
                    f"last one only {elapsed:.0f}s ago"
                )
        except (ValueError, AttributeError):
            pass

    return {
        "loop_detected": loop_detected,
        "loop_reason": loop_reason,
        "escalation_path": escalation_path,
    }
