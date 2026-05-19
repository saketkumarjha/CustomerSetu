"""
RBI Compliance Reporting Endpoints

Simulates what a real bank submits to RBI's SCORES portal.

Endpoints:
  GET /api/v1/rbi/report          — Aggregate compliance report
  GET /api/v1/rbi/pending         — Complaints approaching TAT breach
  GET /api/v1/rbi/categories      — All RBI category definitions
  POST /api/v1/rbi/log/{id}       — Mark a complaint as reported to RBI

For POC: returns structured JSON.
For Production: generates PDF and submits to RBI SCORES API.
"""

from fastapi import APIRouter, HTTPException, Query, Path, status
from datetime import datetime, timezone, timedelta


def _parse_date_param(value: str, param_name: str) -> str:
    """Validate and normalise an ISO date query parameter, raising 422 on bad input."""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{
                "loc": ["query", param_name],
                "msg": f"Invalid {param_name} format. Expected ISO 8601 (e.g. '2025-01-01T00:00:00Z').",
                "type": "value_error.datetime",
            }],
        )
from app.db.supabase_client import get_supabase
from app.services.rbi.categories import (
    RBICategory,
    CATEGORY_LABELS,
    RBI_REPORTABLE_CATEGORIES,
    SUPERVISOR_OVERRIDE_ALWAYS_HUMAN,
)
from app.services.rbi.tat_rules import TAT_RULES, DEFAULT_TAT

router = APIRouter()


@router.get(
    "/report",
    summary="Generate RBI compliance summary report",
    description=(
        "Returns a structured compliance report of all RBI-reportable complaints "
        "within the specified date range. Simulates RBI SCORES portal submission."
    ),
)
async def get_rbi_report(
    from_date: str = Query(
        default=None,
        description="Start date ISO format (default: 30 days ago)"
    ),
    to_date: str = Query(
        default=None,
        description="End date ISO format (default: now)"
    ),
):
    """
    Aggregate RBI compliance report.

    Covers:
    - Total RBI-reportable complaints in period
    - Breakdown by RBI category
    - TAT compliance rate (resolved within deadline)
    - Pending complaints with breach risk
    - Auto vs human routing stats
    - Override rule trigger frequency
    """
    supabase = get_supabase()

    # Set default date range — 30 days
    now = datetime.now(timezone.utc)
    if not from_date:
        from_dt = now - timedelta(days=30)
        from_date = from_dt.isoformat()
    else:
        from_date = _parse_date_param(from_date, "from_date")
    if not to_date:
        to_date = now.isoformat()
    else:
        to_date = _parse_date_param(to_date, "to_date")

    # Fetch all complaints in date range
    all_result = (
        supabase.table("complaints")
        .select(
            "complaint_id, category, compliance_category, is_rbi_reportable, "
            "route, pipeline_status, severity, sentiment, created_at, "
            "rbi_tat_deadline, status"
        )
        .gte("created_at", from_date)
        .lte("created_at", to_date)
        .execute()
    )

    all_complaints = all_result.data or []

    # Split into reportable and non-reportable
    rbi_complaints = [c for c in all_complaints if c.get("is_rbi_reportable")]
    non_rbi = [c for c in all_complaints if not c.get("is_rbi_reportable")]

    # Category breakdown
    category_breakdown = {}
    for c in rbi_complaints:
        cat = c.get("compliance_category", "NOT_APPLICABLE")
        label = CATEGORY_LABELS.get(RBICategory(cat) if cat in [e.value for e in RBICategory] else RBICategory.NOT_APPLICABLE, cat)
        if cat not in category_breakdown:
            category_breakdown[cat] = {
                "rbi_category": cat,
                "display_label": label,
                "total_count": 0,
                "human_review_count": 0,
                "auto_respond_count": 0,
                "resolved_count": 0,
                "pending_count": 0,
                "tat_breached_count": 0,
            }
        category_breakdown[cat]["total_count"] += 1
        if c.get("route") == "human_review":
            category_breakdown[cat]["human_review_count"] += 1
        else:
            category_breakdown[cat]["auto_respond_count"] += 1
        if c.get("status") in ("resolved", "closed"):
            category_breakdown[cat]["resolved_count"] += 1
        else:
            category_breakdown[cat]["pending_count"] += 1

        # Check TAT breach
        tat_deadline = c.get("rbi_tat_deadline")
        if tat_deadline:
            try:
                deadline_dt = datetime.fromisoformat(tat_deadline.replace("Z", "+00:00"))
                if now > deadline_dt and c.get("status") not in ("resolved", "closed"):
                    category_breakdown[cat]["tat_breached_count"] += 1
            except Exception:
                pass

    # TAT compliance calculation
    resolved_rbi = [c for c in rbi_complaints if c.get("status") in ("resolved", "closed")]
    tat_breached = sum(
        1 for c in rbi_complaints
        if c.get("rbi_tat_deadline") and c.get("status") not in ("resolved", "closed")
        and _is_tat_breached(c.get("rbi_tat_deadline"), now)
    )

    tat_compliance_rate = (
        round((len(rbi_complaints) - tat_breached) / max(len(rbi_complaints), 1) * 100, 2)
        if rbi_complaints else 100.0
    )

    # Routing stats
    human_review_count = sum(1 for c in all_complaints if c.get("route") == "human_review")
    auto_respond_count = sum(1 for c in all_complaints if c.get("route") == "auto_respond")

    # Severity distribution
    severity_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for c in all_complaints:
        sev = c.get("severity", 3)
        if sev in severity_dist:
            severity_dist[sev] += 1

    return {
        "report_metadata": {
            "generated_at": now.isoformat(),
            "period_from": from_date,
            "period_to": to_date,
            "report_type": "RBI_COMPLIANCE_SUMMARY",
            "generated_by": "Unified Complaint Dashboard — AI Pipeline v2.0",
        },
        "summary": {
            "total_complaints": len(all_complaints),
            "rbi_reportable_complaints": len(rbi_complaints),
            "non_rbi_complaints": len(non_rbi),
            "tat_compliance_rate_percent": tat_compliance_rate,
            "tat_breached_count": tat_breached,
            "human_review_count": human_review_count,
            "auto_respond_count": auto_respond_count,
            "auto_respond_rate_percent": round(
                auto_respond_count / max(len(all_complaints), 1) * 100, 2
            ),
        },
        "severity_distribution": {
            f"severity_{k}": v for k, v in severity_dist.items()
        },
        "rbi_category_breakdown": list(category_breakdown.values()),
        "compliance_status": (
            "COMPLIANT" if tat_compliance_rate >= 95
            else "AT_RISK" if tat_compliance_rate >= 80
            else "NON_COMPLIANT"
        ),
        "compliance_notes": _build_compliance_notes(
            tat_compliance_rate, tat_breached, rbi_complaints
        ),
    }


@router.get(
    "/pending",
    summary="Complaints approaching or breaching RBI TAT deadline",
)
async def get_pending_rbi_complaints(
    hours_threshold: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Alert threshold — flag complaints with TAT deadline within this many hours (1–720)"
    ),
):
    """
    Returns RBI-reportable complaints that are:
    1. Already past their TAT deadline (BREACHED)
    2. Within {hours_threshold} hours of TAT deadline (WARNING)

    Used by compliance team to prioritise and escalate.
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    warning_cutoff = now + timedelta(hours=hours_threshold)

    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, compliance_category, route, status, "
            "severity, created_at, rbi_tat_deadline, category"
        )
        .eq("is_rbi_reportable", True)
        .not_.in_("status", ["resolved", "closed"])
        .execute()
    )

    complaints = result.data or []
    breached = []
    warning = []

    for c in complaints:
        tat_str = c.get("rbi_tat_deadline")
        if not tat_str:
            continue
        try:
            deadline = datetime.fromisoformat(tat_str.replace("Z", "+00:00"))
            hours_remaining = (deadline - now).total_seconds() / 3600

            entry = {
                **c,
                "hours_remaining": round(hours_remaining, 1),
                "deadline_readable": deadline.strftime("%Y-%m-%d %H:%M UTC"),
                "tat_rules": _get_tat_summary(c.get("compliance_category", "")),
            }

            if hours_remaining <= 0:
                entry["alert_level"] = "BREACHED"
                breached.append(entry)
            elif hours_remaining <= hours_threshold:
                entry["alert_level"] = "WARNING"
                warning.append(entry)

        except Exception:
            continue

    # Sort by urgency
    breached.sort(key=lambda x: x["hours_remaining"])
    warning.sort(key=lambda x: x["hours_remaining"])

    return {
        "generated_at": now.isoformat(),
        "alert_threshold_hours": hours_threshold,
        "summary": {
            "total_pending_rbi": len(complaints),
            "breached_count": len(breached),
            "warning_count": len(warning),
            "safe_count": len(complaints) - len(breached) - len(warning),
        },
        "breached": breached,
        "approaching_breach": warning,
    }


@router.get(
    "/categories",
    summary="All RBI complaint categories with metadata",
)
async def get_rbi_categories():
    """
    Returns all 14 RBI category definitions with:
    - TAT rules and penalty information
    - Whether supervisor override applies
    - Regulatory reference
    """
    categories = []

    for cat in RBICategory:
        if cat == RBICategory.NOT_APPLICABLE:
            continue

        tat = TAT_RULES.get(cat, DEFAULT_TAT)
        is_always_human = cat in SUPERVISOR_OVERRIDE_ALWAYS_HUMAN
        is_reportable = cat in RBI_REPORTABLE_CATEGORIES

        categories.append({
            "category_code": cat.value,
            "display_label": CATEGORY_LABELS.get(cat, cat.value),
            "is_rbi_reportable": is_reportable,
            "supervisor_override_always_human": is_always_human,
            "sla_label": tat.get("sla_label", "30 days"),
            "resolution_hours": tat.get("resolution_hours", 720),
            "acknowledgement_hours": tat.get("acknowledgement_hours", 72),
            "penalty_per_day": tat.get("penalty_per_day", 0),
            "penalty_description": tat.get("penalty_description", "N/A"),
        })

    return {
        "total_categories": len(categories),
        "always_human_review_count": sum(
            1 for c in categories if c["supervisor_override_always_human"]
        ),
        "categories": categories,
    }


@router.post(
    "/log/{complaint_id}",
    summary="Mark complaint as reported to RBI",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Complaint not found"},
        409: {"description": "Complaint is not RBI-reportable"},
        500: {"description": "Database error inserting RBI log entry"},
    },
)
async def mark_as_rbi_reported(complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)")):
    """
    Mark a complaint as formally reported to RBI SCORES portal.
    In production: this would also trigger the actual SCORES API submission.
    For POC: updates the rbi_reportable_log table.
    """
    supabase = get_supabase()

    # Verify complaint exists and is RBI reportable
    result = (
        supabase.table("complaints")
        .select("complaint_id, compliance_category, is_rbi_reportable, rbi_tat_deadline")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint {complaint_id} not found."
        )

    complaint = result.data[0]

    if not complaint.get("is_rbi_reportable"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Complaint {complaint_id} is not RBI-reportable."
        )

    # Guard against duplicate log entries — return 200 (idempotent) if already logged
    existing_log = (
        supabase.table("rbi_reportable_log")
        .select("complaint_id, reported_at")
        .eq("complaint_id", complaint_id)
        .limit(1)
        .execute()
    )
    if existing_log.data:
        return {
            "complaint_id": complaint_id,
            "rbi_category": complaint.get("compliance_category"),
            "reported_at": existing_log.data[0].get("reported_at"),
            "status": "already_logged",
            "message": f"Complaint {complaint_id} was already reported to RBI.",
        }

    # Insert into rbi_reportable_log
    now = datetime.now(timezone.utc)
    try:
        supabase.table("rbi_reportable_log").insert({
            "complaint_id": complaint_id,
            "rbi_category": complaint.get("compliance_category"),
            "tat_deadline": complaint.get("rbi_tat_deadline"),
            "escalated": True,
            "reported_at": now.isoformat(),
        }).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log RBI report: {str(e)}"
        )

    return {
        "complaint_id": complaint_id,
        "rbi_category": complaint.get("compliance_category"),
        "reported_at": now.isoformat(),
        "status": "logged",
        "message": (
            f"Complaint {complaint_id} marked as reported to RBI. "
            f"In production, this would submit to SCORES portal."
        ),
    }


# ── Helper functions ──────────────────────────────────────────────────────────

def _is_tat_breached(tat_deadline_str: str, now: datetime) -> bool:
    try:
        deadline = datetime.fromisoformat(tat_deadline_str.replace("Z", "+00:00"))
        return now > deadline
    except Exception:
        return False


def _get_tat_summary(compliance_category: str) -> dict:
    try:
        cat_enum = RBICategory(compliance_category)
        tat = TAT_RULES.get(cat_enum, DEFAULT_TAT)
        return {
            "sla_label": tat.get("sla_label"),
            "penalty_per_day": tat.get("penalty_per_day", 0),
        }
    except ValueError:
        return {"sla_label": "30 days", "penalty_per_day": 0}


def _build_compliance_notes(
    tat_rate: float,
    breached: int,
    rbi_complaints: list,
) -> list[str]:
    notes = []
    if tat_rate >= 95:
        notes.append("✅ TAT compliance is within RBI acceptable range (≥95%)")
    elif tat_rate >= 80:
        notes.append("⚠️ TAT compliance is below ideal — review pending resolutions")
    else:
        notes.append("🚨 TAT compliance is critically low — immediate action required")

    if breached > 0:
        notes.append(
            f"🚨 {breached} complaint(s) have breached TAT deadline — "
            f"potential RBI penalty applicable"
        )

    fraud_count = sum(
        1 for c in rbi_complaints
        if c.get("compliance_category") == "UNAUTHORIZED_TRANSACTION_FRAUD"
    )
    if fraud_count > 0:
        notes.append(
            f"⚠️ {fraud_count} unauthorized transaction case(s) — "
            f"RBI Limiting Liability guidelines apply"
        )

    return notes