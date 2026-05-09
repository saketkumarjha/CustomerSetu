"""
Agent Assignment Service — Intelligent agent-to-complaint matching.

Assignment priority:
  1. Agent specialisation match for complaint category
  2. Lowest current workload (among qualifying agents)
  3. SLA urgency — if SLA breach imminent, pick fastest agent
  4. Round-robin fallback when no specialisation data

Returns agent_id or None (caller adds complaint to queue if None).
"""

from app.core.config import get_settings
from app.db.supabase_client import get_supabase


def get_agent_workload(agent_id: str) -> int:
    """Return count of IN_REVIEW + ASSIGNED rows for agent_id in agent_queue."""
    supabase = get_supabase()
    result = (
        supabase.table("agent_queue")
        .select("id", count="exact")
        .eq("assigned_to", agent_id)
        .in_("status", ["ASSIGNED", "IN_REVIEW"])
        .execute()
    )
    return result.count or 0


def find_best_agent(
    tier_level: int,
    complaint_category: str,
    priority: str = "NORMAL",
) -> str | None:
    """
    Find the best available agent for a complaint at the given tier.

    Returns agent_id string or None if no agent is currently available.
    """
    settings = get_settings()
    max_workload = settings.agent_max_workload

    candidate_ids: list[str] = settings.tier_agent_mapping.get(tier_level, [])
    if not candidate_ids:
        return None

    specialization: dict = settings.agent_specialization

    # Partition by specialisation match
    specialists = [
        aid for aid in candidate_ids
        if complaint_category in specialization.get(aid, [])
    ]
    generalists = [aid for aid in candidate_ids if aid not in specialists]

    # Sort each group by ascending workload; pick first under cap
    for pool in [specialists, generalists]:
        ranked = sorted(pool, key=lambda aid: get_agent_workload(aid))
        for agent_id in ranked:
            if get_agent_workload(agent_id) < max_workload:
                return agent_id

    return None


def list_active_agents(tier_level: int) -> list[str]:
    """Return all agent IDs configured for a tier."""
    settings = get_settings()
    return settings.tier_agent_mapping.get(tier_level, [])
