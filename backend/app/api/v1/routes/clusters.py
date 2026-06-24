"""
Incident alert endpoint.
Returns the latest scored snapshot for each active cluster so the
frontend can broadcast emerging issues to all agents.
"""
import logging
from fastapi import APIRouter, Query

from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()

_PRIORITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


@router.get("/alerts", summary="Active incident alerts from predictive ML model")
async def get_incident_alerts(
    min_priority: str = Query(
        "low",
        description="Minimum alert priority to include: low | medium | high | critical",
    ),
):
    """
    Returns one entry per active cluster (latest snapshot only), filtered by
    min_priority and sorted critical-first.  Each entry carries a `departments`
    list derived from the routing table so the frontend can show which team
    should act.
    """
    from app.services.incident_scorer import ROUTING_TABLE, DEFAULT_DEPARTMENTS, _MODEL_LOADED

    supabase = get_supabase()

    try:
        result = (
            supabase.table("complaint_clusters")
            .select(
                "cluster_id, event_type, product, region, alert_priority, "
                "risk_score, growth_probability, predicted_impact_customers, "
                "confidence_score, distinct_customers_24h, rbi_reportable_ratio, "
                "last_seen_at, snapshot_time"
            )
            .in_("alert_priority", ["low", "medium", "high", "critical"])
            .eq("status", "active")
            .order("snapshot_time", desc=True)
            .limit(500)
            .execute()
        )
    except Exception:
        logger.exception("[CLUSTERS] Failed to fetch alerts")
        return {"alerts": [], "total": 0}

    rows = result.data or []

    # Keep only the most-recent snapshot per cluster
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        cid = row.get("cluster_id")
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(row)

    # Apply minimum priority filter
    min_rank = _PRIORITY_RANK.get(min_priority.lower(), 1)
    alerts = [
        r for r in deduped
        if _PRIORITY_RANK.get((r.get("alert_priority") or "").lower(), 0) >= min_rank
    ]

    # Sort: highest priority first, then by risk_score descending
    alerts.sort(
        key=lambda r: (
            -_PRIORITY_RANK.get((r.get("alert_priority") or "").lower(), 0),
            -(r.get("risk_score") or 0),
        )
    )

    # Attach department routing from the ML routing table
    for alert in alerts:
        et = alert.get("event_type") or "unknown"
        alert["departments"] = (
            ROUTING_TABLE.get(et, DEFAULT_DEPARTMENTS) if _MODEL_LOADED else []
        )

    return {"alerts": alerts, "total": len(alerts)}
