"""
Escalation Cost Optimizer

Determines which agents to re-run during tier transitions.
Agents 1-6 are never re-run (their outputs don't change with tier).
Agent 9 (grounding) is skipped if the draft response didn't change significantly
— saves ~1 LLM call per escalation when the response is similar.
"""


def determine_agents_to_rerun(
    from_tier: int,
    to_tier: int,
    previous_draft: str = "",
    new_draft: str = "",
) -> list:
    """
    Returns ordered list of agent numbers to re-run.
    Always includes: 7 (RAG), 8 (Resolution), 10 (Router), 10.5 (Escalation).
    Conditionally includes: 9 (Grounding) when response changed > 30%.
    """
    agents = [7, 8, 10, "10.5"]

    if _response_changed_significantly(previous_draft, new_draft):
        agents.insert(2, 9)

    return agents


def _response_changed_significantly(old: str, new: str, threshold: float = 0.30) -> bool:
    if not old or not new:
        return True
    old_words = set(old.lower().split())
    new_words = set(new.lower().split())
    if not old_words:
        return True
    overlap = len(old_words & new_words) / len(old_words)
    return (1 - overlap) > threshold
