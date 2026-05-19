"""
SLA Breach Predictor Endpoints

GET /api/v1/sla/at-risk      — All complaints predicted to breach SLA
GET /api/v1/sla/predict/{id} — Prediction for a single complaint
GET /api/v1/sla/summary      — Overall SLA health dashboard
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Path
from datetime import datetime, timezone
from app.db.supabase_client import get_supabase
from app.services.sla_predictor import predict_sla_breach

router = APIRouter()

# Single source of truth for routes that count as "human review / needs attention".
# Both /at-risk and /summary must use this constant so their counts stay in sync.
HUMAN_REVIEW_ROUTES = ["HUMAN", "human_review", "ESCALATE", "escalate", "escalation_human_review"]


@router.get(
    "/at-risk",
    summary="All complaints predicted to breach SLA — ranked by risk",
)
async def get_sla_at_risk(
    risk_threshold: float = Query(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum breach probability to include (0.0-1.0)"
    ),
    include_low: Optional[str] = Query(
        default=None,
        description="Include LOW risk complaints in results (true/false)",
        pattern="^(true|false|null)$"
    ),
):
    """
    Returns all open complaints predicted to breach their SLA,
    ranked by breach probability (highest risk first).

    This endpoint powers the 'SLA Breach Predictor' feature.
    The system predicts breaches 2-6 hours before they happen.

    Frontend usage:
    - Show as a priority queue for operations team
    - Auto-escalate CRITICAL risk complaints
    - Send alerts for HIGH risk complaints
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    # Fetch all open human_review complaints with SLA info
    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, category, severity, sla_hours, "
            "created_at, route, status, rbi_tat_deadline, "
            "compliance_category, is_rbi_reportable, channel"
        )
        .in_("route", HUMAN_REVIEW_ROUTES)
        .eq("pipeline_status", "complete")
        .not_.in_("status", ["closed", "resolved", "auto_closed"])
        .execute()
    )

    complaints = result.data or []
    include_low_bool = include_low is not None and include_low.lower() == "true"

    if not complaints:
        return {
            "generated_at": now.isoformat(),
            "message": "No open human review complaints found.",
            "total_open_complaints": 0,
            "at_risk_count": 0,
            "risk_summary": {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0},
            "system_alert": None,
            "predictions": [],
        }

    # Current queue depth — used in all predictions
    queue_depth = len(complaints)

    predictions = []
    for c in complaints:
        sla_hours = c.get("sla_hours") or 720
        prediction = predict_sla_breach(
            complaint_id=c["complaint_id"],
            category=c.get("category", "General Banking"),
            severity=c.get("severity") or 3,
            sla_hours=sla_hours,
            created_at=c.get("created_at", now.isoformat()),
            current_queue_depth=queue_depth,
        )

        # Filter by threshold — LOW is excluded unless include_low=True.
        # Additionally apply the numeric risk_threshold to MODERATE predictions.
        if prediction["risk_level"] == "LOW" and not include_low_bool:
            continue
        if prediction["risk_level"] == "MODERATE" and prediction["breach_probability"] < risk_threshold:
            continue

        predictions.append({
            **prediction,
            "category": c.get("category"),
            "channel": c.get("channel"),
            "severity": c.get("severity"),
            "is_rbi_reportable": c.get("is_rbi_reportable", False),
            "compliance_category": c.get("compliance_category"),
            "rbi_tat_deadline": c.get("rbi_tat_deadline"),
        })

    # Sort by breach probability descending
    predictions.sort(key=lambda x: x["breach_probability"], reverse=True)

    # Risk level summary
    risk_summary = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
    for p in predictions:
        risk_summary[p["risk_level"]] = risk_summary.get(p["risk_level"], 0) + 1

    return {
        "generated_at": now.isoformat(),
        "total_open_complaints": queue_depth,
        "at_risk_count": len(predictions),
        "risk_summary": risk_summary,
        "system_alert": _build_system_alert(risk_summary),
        "predictions": predictions,
    }


@router.get(
    "/predict/{complaint_id}",
    summary="SLA breach prediction for a single complaint",
    responses={404: {"description": "Complaint not found"}},
)
async def predict_single_complaint(complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)")):
    """
    Returns detailed SLA breach prediction for one complaint.
    Includes full signal breakdown for transparency (XAI).
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, category, severity, sla_hours, "
            "created_at, route, status, rbi_tat_deadline, "
            "is_rbi_reportable, compliance_category"
        )
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not result.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Complaint {complaint_id} not found")

    c = result.data[0]

    # Get current queue depth
    queue_result = (
        supabase.table("complaints")
        .select("complaint_id", count="exact")
        .in_("route", HUMAN_REVIEW_ROUTES)
        .eq("pipeline_status", "complete")
        .not_.in_("status", ["closed", "resolved", "auto_closed"])
        .execute()
    )
    queue_depth = queue_result.count or 1

    prediction = predict_sla_breach(
        complaint_id=c["complaint_id"],
        category=c.get("category", "General Banking"),
        severity=c.get("severity") or 3,
        sla_hours=c.get("sla_hours") or 720,
        created_at=c.get("created_at", now.isoformat()),
        current_queue_depth=queue_depth,
    )

    return {
        **prediction,
        "rbi_tat_deadline": c.get("rbi_tat_deadline"),
        "is_rbi_reportable": c.get("is_rbi_reportable"),
        "current_queue_depth": queue_depth,
        "model_description": (
            "Weighted scoring model using 6 signals: "
            "time elapsed (35%), queue pressure (20%), "
            "severity (15%), time of day (10%), "
            "day of week (10%), historical resolution (10%)"
        ),
    }


@router.get(
    "/summary",
    summary="Overall SLA health summary",
)
async def get_sla_summary():
    """
    High-level SLA health for the dashboard header.
    Quick view of system-wide SLA status.
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    # All open complaints
    open_result = (
        supabase.table("complaints")
        .select(
            "complaint_id, category, severity, sla_hours, "
            "created_at, route, rbi_tat_deadline, status"
        )
        .eq("pipeline_status", "complete")
        .not_.in_("status", ["closed", "resolved"])
        .execute()
    )

    open_complaints = open_result.data or []
    _route_set = set(HUMAN_REVIEW_ROUTES)
    queue_depth = len([
        c for c in open_complaints
        if (c.get("route") or "") in _route_set
    ])

    # Count RBI TAT breaches
    rbi_breached = 0
    rbi_at_risk = 0
    for c in open_complaints:
        tat = c.get("rbi_tat_deadline")
        if not tat:
            continue
        try:
            deadline = datetime.fromisoformat(tat.replace("Z", "+00:00"))
            hours_left = (deadline - now).total_seconds() / 3600
            if hours_left < 0:
                rbi_breached += 1
            elif hours_left < 24:
                rbi_at_risk += 1
        except Exception:
            continue

    # Run predictions on human_review complaints
    human_review = [
        c for c in open_complaints
        if (c.get("route") or "") in _route_set
    ]
    critical_count = 0
    high_count = 0

    for c in human_review[:50]:  # cap at 50 for performance
        pred = predict_sla_breach(
            complaint_id=c["complaint_id"],
            category=c.get("category", "General Banking"),
            severity=c.get("severity") or 3,
            sla_hours=c.get("sla_hours") or 720,
            created_at=c.get("created_at", now.isoformat()),
            current_queue_depth=queue_depth,
        )
        if pred["risk_level"] == "CRITICAL":
            critical_count += 1
        elif pred["risk_level"] == "HIGH":
            high_count += 1

    return {
        "generated_at": now.isoformat(),
        "overall_health": _overall_health(critical_count, rbi_breached, high_count),
        "open_complaints": len(open_complaints),
        "human_review_queue": queue_depth,
        "rbi_tat_breached": rbi_breached,
        "rbi_tat_at_risk_24h": rbi_at_risk,
        "predicted_breach": {
            "critical": critical_count,
            "high": high_count,
            "total_at_risk": critical_count + high_count,
        },
        "action_required": critical_count > 0 or rbi_breached > 0,
    }


def _build_system_alert(risk_summary: dict) -> str | None:
    critical = risk_summary.get("CRITICAL", 0)
    high = risk_summary.get("HIGH", 0)
    if critical > 0:
        return (
            f"🚨 CRITICAL: {critical} complaint(s) will breach SLA imminently. "
            f"Immediate agent assignment required."
        )
    if high > 0:
        return (
            f"⚠️ WARNING: {high} complaint(s) have high breach probability. "
            f"Prioritise in agent queue."
        )
    return None


def _overall_health(critical: int, rbi_breached: int, high: int = 0) -> str:
    if critical > 0 or rbi_breached > 0:
        return "CRITICAL"
    if high > 0:
        return "AT_RISK"
    return "HEALTHY"