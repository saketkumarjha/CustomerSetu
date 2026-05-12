"""
Dashboard Aggregator — Pre-compute agent and team metrics for the dashboard.
"""

import time
import logging

from app.db.supabase_client import get_supabase
from app.services.metrics_service import calculate_agent_efficiency
from app.utils.postgrest_errors import is_missing_relation_error

logger = logging.getLogger(__name__)


def _execute_with_retry(query, retries: int = 3, delay: float = 0.3):
    """
    Execute a Supabase query with retry on transient socket errors.
    Handles WinError 10035 (WSAEWOULDBLOCK) which is common on Windows
    with HTTP/2 connection pools under load.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            return query.execute()
        except Exception as exc:
            msg = str(exc).lower()
            # Retry only on transient network/socket errors
            if any(k in msg for k in ("10035", "readError", "read error", "connection", "timeout")):
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
                    logger.warning("[DB] Transient socket error (attempt %d/%d): %s", attempt + 1, retries, exc)
                continue
            raise  # non-transient — re-raise immediately
    raise last_exc  # all retries exhausted


def get_agent_metrics(
    agent_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """
    Return aggregated performance metrics for a single agent.
    """
    supabase = get_supabase()

    efficiency = calculate_agent_efficiency(agent_id, date_from, date_to)

    # Current workload
    try:
        workload_result = _execute_with_retry(
            supabase.table("agent_queue")
            .select("id", count="exact")
            .eq("assigned_to", agent_id)
            .in_("status", ["ASSIGNED", "IN_REVIEW"])
        )
        current_workload = workload_result.count or 0
    except Exception as exc:
        if not is_missing_relation_error(exc):
            logger.warning("[METRICS] workload query failed for %s: %s", agent_id, exc)
        current_workload = 0

    # Category breakdown
    complaint_ids: list[str] = []
    try:
        query = (
            supabase.table("agent_assignments")
            .select("complaint_id")
            .eq("agent_id", agent_id)
            .not_.is_("completed_at", "null")
        )
        if date_from:
            query = query.gte("completed_at", date_from)
        if date_to:
            query = query.lte("completed_at", date_to)
        assign_result = _execute_with_retry(query)
        complaint_ids = [r["complaint_id"] for r in (assign_result.data or [])]
    except Exception as exc:
        if not is_missing_relation_error(exc):
            logger.warning("[METRICS] assignments query failed for %s: %s", agent_id, exc)

    categories_handled: dict = {}
    if complaint_ids:
        cat_result = _execute_with_retry(
            supabase.table("complaints")
            .select("category")
            .in_("complaint_id", complaint_ids)
        )
        for row in cat_result.data or []:
            cat = row.get("category") or "Unknown"
            categories_handled[cat] = categories_handled.get(cat, 0) + 1

    avg_seconds = efficiency.get("avg_review_time_seconds")
    avg_min_str = (
        f"{round(avg_seconds / 60, 1)} min" if avg_seconds else "N/A"
    )

    return {
        "agent_id":            agent_id,
        "total_reviewed":      efficiency["total_reviewed"],
        "avg_review_time":     avg_min_str,
        "acceptance_rate":     efficiency.get("acceptance_rate"),
        "edit_rate":           efficiency.get("edit_rate"),
        "rejection_rate":      efficiency.get("rejection_rate"),
        "escalation_rate":     efficiency.get("escalation_rate"),
        "current_workload":    current_workload,
        "categories_handled":  categories_handled,
    }


def get_team_metrics(
    tier_level: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """
    Return aggregated metrics for all agents at tier_level.
    """
    from app.core.config import get_settings
    settings = get_settings()
    agent_ids = settings.tier_agent_mapping.get(tier_level, [])

    team_stats = []
    for aid in agent_ids:
        m = get_agent_metrics(aid, date_from, date_to)
        team_stats.append(m)

    total_reviewed = sum(s["total_reviewed"] for s in team_stats)

    # Queue size for this tier
    supabase = get_supabase()
    try:
        q_result = _execute_with_retry(
            supabase.table("agent_queue")
            .select("id", count="exact")
            .eq("tier_level", tier_level)
            .in_("status", ["QUEUED", "ASSIGNED", "IN_REVIEW"])
        )
        queue_size = q_result.count or 0
    except Exception as exc:
        if not is_missing_relation_error(exc):
            logger.warning("[METRICS] queue_size query failed for tier %d: %s", tier_level, exc)
        queue_size = 0

    return {
        "tier_level":     tier_level,
        "agent_count":    len(agent_ids),
        "total_reviewed": total_reviewed,
        "queue_size":     queue_size,
        "agents":         team_stats,
    }
