"""
360° Customer View routes.

GET /api/v1/customers          — paginated customer card list with aggregated complaint stats
GET /api/v1/customers/{cif_id} — full customer detail with all complaints + AI insights
"""

from fastapi import APIRouter, Query, HTTPException
from app.db.supabase_client import get_supabase
from collections import Counter
from datetime import datetime, timezone

router = APIRouter()


def _name_from_email(email: str | None) -> str:
    """Derive a display name from email (before @, capitalised)."""
    if not email:
        return "Unknown"
    local = email.split("@")[0]
    return " ".join(p.capitalize() for p in local.replace(".", " ").replace("_", " ").split())


def _compute_stats(complaints: list[dict]) -> dict:
    total = len(complaints)
    active = sum(1 for c in complaints if c.get("status") not in ("Resolved", "resolved", "merged", "Merged") and not c.get("merged_into"))
    resolved = sum(1 for c in complaints if c.get("status") in ("Resolved", "resolved"))
    merged = sum(1 for c in complaints if c.get("merged_into"))
    last = max((c.get("created_at", "") for c in complaints), default=None) if complaints else None
    last_status = None
    if last:
        last_c = max(complaints, key=lambda c: c.get("created_at", ""))
        last_status = last_c.get("status")
    return {
        "total_complaints": total,
        "active_complaints": active,
        "resolved_complaints": resolved,
        "merged_complaints": merged,
        "last_complaint_date": last[:10] if last else None,
        "last_complaint_status": last_status,
    }


def _ai_insights(complaints: list[dict]) -> list[str]:
    if not complaints:
        return []
    insights = []
    cats = Counter(c.get("category") for c in complaints if c.get("category"))
    if cats:
        top_cat, top_count = cats.most_common(1)[0]
        insights.append(f"Frequent complaints in {top_cat} category ({top_count} of {len(complaints)})")
    sentiments = [c.get("sentiment", "").lower() for c in complaints if c.get("sentiment")]
    negative = sum(1 for s in sentiments if s in ("angry", "furious", "frustrated", "upset", "stressed"))
    if negative > 0:
        insights.append(f"{negative} complaint{'s' if negative > 1 else ''} with negative sentiment")
    escalated = sum(1 for c in complaints if c.get("route") == "ESCALATE" or c.get("status") == "Escalated")
    if escalated:
        insights.append(f"{escalated} complaint{'s' if escalated > 1 else ''} escalated in history")
    merged = sum(1 for c in complaints if c.get("merged_into"))
    if merged:
        insights.append(f"{merged} duplicate complaint{'s' if merged > 1 else ''} merged into parent")
    if not insights:
        insights.append("No significant patterns detected")
    return insights


@router.get("", summary="List customers with aggregated complaint stats")
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    search: str = Query("", description="Search by email, phone, account_number, or cif_id"),
    status_filter: str = Query("", alias="status"),
    channel_filter: str = Query("", alias="channel"),
):
    supabase = get_supabase()

    # Fetch customers
    q = supabase.table("customers").select("*")
    if search:
        # Supabase doesn't support OR easily via SDK; fetch all and filter in Python
        pass
    customers_resp = q.execute()
    customers = customers_resp.data or []

    # Apply search filter in Python
    if search:
        s = search.lower()
        customers = [
            c for c in customers
            if s in (c.get("email") or "").lower()
            or s in (c.get("phone") or "").lower()
            or s in (c.get("account_number") or "").lower()
            or s in (c.get("cif_id") or "").lower()
            or s in _name_from_email(c.get("email")).lower()
        ]

    # Fetch all complaints grouped by cif_id
    complaints_resp = supabase.table("complaints").select(
        "complaint_id, cif_id, status, channel, created_at, merged_into, route, sentiment, category"
    ).execute()
    all_complaints = complaints_resp.data or []

    complaints_by_cif: dict[str, list] = {}
    for c in all_complaints:
        cif = c.get("cif_id")
        if cif:
            complaints_by_cif.setdefault(cif, []).append(c)

    # Build card list
    cards = []
    for cust in customers:
        cif_id = cust["cif_id"]
        comps = complaints_by_cif.get(cif_id, [])

        # Channel filter
        if channel_filter:
            comp_channels = {c.get("channel", "").lower() for c in comps}
            if channel_filter.lower() not in comp_channels:
                continue

        stats = _compute_stats(comps)

        # Status filter (on last complaint status)
        if status_filter and stats["last_complaint_status"]:
            if stats["last_complaint_status"].lower() != status_filter.lower():
                continue

        cards.append({
            "cif_id": cif_id,
            "name": _name_from_email(cust.get("email")),
            "email": cust.get("email"),
            "phone": cust.get("phone"),
            "account_number": cust.get("account_number"),
            "verified": cust.get("verified", False),
            "customer_since": (cust.get("created_at") or "")[:10] or None,
            **stats,
        })

    # Sort: most recently active first
    cards.sort(key=lambda c: c.get("last_complaint_date") or "", reverse=True)

    total = len(cards)
    start = (page - 1) * page_size
    page_cards = cards[start: start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "customers": page_cards,
    }


@router.get("/{cif_id}/summary", summary="Get cached CIF narrative summary")
def get_cif_summary(cif_id: str):
    """
    Return the cached CIF-level narrative summary.
    Returns summary_text: null when no summary exists yet — frontend handles this gracefully.
    Never returns 404; always returns a valid JSON object.
    """
    supabase = get_supabase()
    result = (
        supabase.table("cif_summaries")
        .select("cif_id, summary_text, complaint_count, last_updated")
        .eq("cif_id", cif_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return {
        "cif_id": cif_id,
        "summary_text": None,
        "complaint_count": 0,
        "last_updated": None,
    }


@router.get("/{cif_id}", summary="Full 360° customer detail")
def get_customer(cif_id: str):
    supabase = get_supabase()

    # Customer profile
    cust_resp = supabase.table("customers").select("*").eq("cif_id", cif_id).execute()
    if not cust_resp.data:
        raise HTTPException(status_code=404, detail=f"Customer {cif_id} not found")
    cust = cust_resp.data[0]

    # All complaints for this customer
    comp_resp = supabase.table("complaints").select(
        "complaint_id, customer_id, channel, category, compliance_category, "
        "is_rbi_reportable, sentiment, severity, urgency_score, escalation_flag, "
        "route, status, pipeline_status, confidence_score, risk_score, "
        "sla_hours, rbi_tat_deadline, created_at, duplicate_status, duplicate_of, "
        "merged_into, is_duplicate, original_text, masked_text, draft_response, "
        "draft_response_text, final_response_text, resolution_type, root_cause, "
        "action_steps, escalation_path, assigned_tier, current_tier, identity_status, cif_id"
    ).eq("cif_id", cif_id).order("created_at", desc=True).execute()
    complaints = comp_resp.data or []

    stats = _compute_stats(complaints)
    insights = _ai_insights(complaints)

    # Category breakdown for donut chart
    cat_counts = Counter(c.get("category") for c in complaints if c.get("category"))
    category_breakdown = [{"category": k, "count": v} for k, v in cat_counts.most_common()]

    # Sentiment trend (chronological)
    sentiment_trend = [
        {"date": c.get("created_at", "")[:10], "sentiment": c.get("sentiment"), "complaint_id": c.get("complaint_id")}
        for c in reversed(complaints)
        if c.get("sentiment")
    ]

    # Communication timeline: derive events from complaint data
    timeline_events = []
    for c in complaints:
        cid = c.get("complaint_id")
        created = c.get("created_at")
        timeline_events.append({"event": "Complaint Received", "complaint_id": cid, "channel": c.get("channel"), "timestamp": created})
        if c.get("pipeline_status") in ("completed", "auto_sent"):
            timeline_events.append({"event": "Auto Acknowledgement", "complaint_id": cid, "channel": c.get("channel"), "timestamp": created})
        if c.get("draft_response") or c.get("draft_response_text") or c.get("final_response_text"):
            timeline_events.append({"event": "Agent Reply", "complaint_id": cid, "channel": c.get("channel"), "timestamp": created})
        if c.get("route") == "ESCALATE" or c.get("status") == "Escalated":
            timeline_events.append({"event": "Escalated", "complaint_id": cid, "tier": c.get("assigned_tier"), "timestamp": created})
        if c.get("status") in ("Resolved", "resolved"):
            timeline_events.append({"event": "Resolved", "complaint_id": cid, "channel": c.get("channel"), "timestamp": created})

    # Sort timeline chronologically
    timeline_events.sort(key=lambda e: e.get("timestamp") or "")

    # Replies: complaints with any response text
    replies = [
        {
            "complaint_id": c.get("complaint_id"),
            "channel": c.get("channel"),
            "reply": c.get("final_response_text") or c.get("draft_response_text") or c.get("draft_response"),
            "route": c.get("route"),
            "timestamp": c.get("created_at"),
        }
        for c in complaints
        if c.get("final_response_text") or c.get("draft_response_text") or c.get("draft_response")
    ]

    # Follow-ups: complaints that are duplicates of another complaint by same customer
    followups = [
        {
            "complaint_id": c.get("complaint_id"),
            "duplicate_of": c.get("duplicate_of"),
            "channel": c.get("channel"),
            "category": c.get("category"),
            "timestamp": c.get("created_at"),
            "status": c.get("status"),
        }
        for c in complaints
        if c.get("duplicate_of") or c.get("is_duplicate")
    ]

    # Notes: escalation_path + explanation_trace per complaint
    notes = []
    for c in complaints:
        if c.get("escalation_path"):
            notes.append({
                "complaint_id": c.get("complaint_id"),
                "type": "escalation",
                "content": c.get("escalation_path"),
                "timestamp": c.get("created_at"),
            })
        if c.get("root_cause"):
            notes.append({
                "complaint_id": c.get("complaint_id"),
                "type": "root_cause",
                "content": c.get("root_cause"),
                "timestamp": c.get("created_at"),
            })
        if c.get("resolution_type"):
            notes.append({
                "complaint_id": c.get("complaint_id"),
                "type": "resolution",
                "content": c.get("resolution_type"),
                "timestamp": c.get("created_at"),
            })

    # Avg resolution time (days) for resolved complaints
    resolved_complaints = [c for c in complaints if c.get("status") in ("Resolved", "resolved")]
    avg_resolution_days = None
    if resolved_complaints and len(resolved_complaints) > 0:
        avg_sla = sum(c.get("sla_hours") or 0 for c in resolved_complaints) / len(resolved_complaints)
        avg_resolution_days = round(avg_sla / 24, 1)

    return {
        "profile": {
            "cif_id": cif_id,
            "name": _name_from_email(cust.get("email")),
            "email": cust.get("email"),
            "phone": cust.get("phone"),
            "account_number": cust.get("account_number"),
            "verified": cust.get("verified", False),
            "customer_since": (cust.get("created_at") or "")[:10] or None,
        },
        "stats": {
            **stats,
            "avg_resolution_days": avg_resolution_days,
        },
        "complaints": complaints,
        "category_breakdown": category_breakdown,
        "sentiment_trend": sentiment_trend,
        "timeline_events": timeline_events,
        "replies": replies,
        "followups": followups,
        "notes": notes,
        "insights": insights,
    }
