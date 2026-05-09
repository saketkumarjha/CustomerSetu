"""
Agent Dashboard API

Endpoints:
  GET  /agent/queue                          — list complaints in agent's tier queue
  GET  /agent/complaint/{id}/context         — full review context for a complaint
  POST /agent/complaint/{id}/action          — ACCEPT / EDIT / REJECT / MANUAL_ESCALATE
  GET  /agent/next-complaint                 — auto-fetch highest priority complaint
  GET  /agent/metrics/{agent_id}             — agent performance metrics
  GET  /agent/team-metrics/{tier_level}      — team metrics for a tier
"""

import logging
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

from app.db.supabase_client import get_supabase
from app.services.agent_context_service import prepare_review_context
from app.services.agent_action_service import (
    handle_accept,
    handle_edit,
    handle_reject,
    handle_manual_escalate,
)
from app.utils.agent_action_validator import validate_action
from app.services.queue_service import (
    get_next_complaint,
    calculate_queue_position,
)
from app.services.dashboard_aggregator import get_agent_metrics, get_team_metrics
from app.services.metrics_service import track_review_started

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class AgentActionRequest(BaseModel):
    agent_id: str
    action: Literal["ACCEPT", "EDIT", "REJECT", "MANUAL_ESCALATE"]
    edited_response: str | None = None
    rejection_reason: str | None = None
    escalation_target_tier: int | None = None
    notes: str = ""


class NextComplaintRequest(BaseModel):
    agent_id: str
    tier_level: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/queue",
    summary="List complaints in the agent queue",
)
def get_queue(
    agent_id: str = Query(..., description="Requesting agent's ID"),
    tier_level: int = Query(..., description="Tier to query"),
    status_filter: str = Query(
        "QUEUED,ASSIGNED,IN_REVIEW",
        description="Comma-separated statuses to include",
    ),
):
    """
    Returns all complaints in the queue for the given tier.

    Response includes total_queue_size, my_assigned, and the sorted complaint list.
    """
    supabase = get_supabase()
    statuses = [s.strip() for s in status_filter.split(",")]

    queue_result = (
        supabase.table("agent_queue")
        .select("*")
        .eq("tier_level", tier_level)
        .in_("status", statuses)
        .order("priority_score", desc=True)
        .execute()
    )
    rows = queue_result.data or []

    complaint_ids = [r["complaint_id"] for r in rows]
    complaints_meta: dict = {}
    if complaint_ids:
        c_result = (
            supabase.table("complaints")
            .select("complaint_id, category, severity, urgency_score, rbi_tat_deadline, status")
            .in_("complaint_id", complaint_ids)
            .execute()
        )
        for c in c_result.data or []:
            complaints_meta[c["complaint_id"]] = c

    my_assigned = 0
    my_in_review = 0
    items = []

    for row in rows:
        cid = row["complaint_id"]
        meta = complaints_meta.get(cid, {})
        if row.get("assigned_to") == agent_id:
            my_assigned += 1
        if row.get("status") == "IN_REVIEW" and row.get("assigned_to") == agent_id:
            my_in_review += 1

        severity = meta.get("severity") or 3
        urgency  = meta.get("urgency_score") or 0

        priority_label = (
            "CRITICAL" if urgency >= 9 or severity == 5 else
            "HIGH"     if urgency >= 7 or severity >= 4 else
            "MEDIUM"   if urgency >= 4 or severity >= 3 else
            "LOW"
        )

        sla_remaining_hours = None
        sla_raw = row.get("sla_deadline") or meta.get("rbi_tat_deadline")
        if sla_raw:
            from datetime import datetime, timezone
            try:
                sla_dt = datetime.fromisoformat(sla_raw.replace("Z", "+00:00"))
                sla_remaining_hours = round(
                    (sla_dt - datetime.now(timezone.utc)).total_seconds() / 3600, 1
                )
            except ValueError:
                pass

        items.append({
            "id":                   cid,
            "queue_status":         row.get("status"),
            "assigned_to":          row.get("assigned_to"),
            "priority":             priority_label,
            "priority_score":       row.get("priority_score"),
            "queue_position":       row.get("queue_position"),
            "sla_remaining_hours":  sla_remaining_hours,
            "sla_deadline":         sla_raw,
            "category":             meta.get("category"),
            "severity":             severity,
            "tier":                 tier_level,
            "estimated_review_time": f"{row.get('estimated_review_time', 12)} min",
        })

    return {
        "total_queue_size": len(rows),
        "my_assigned":      my_assigned,
        "my_in_review":     my_in_review,
        "complaints":       items,
    }


@router.get(
    "/complaint/{complaint_id}/context",
    summary="Full review context for a complaint",
)
def get_complaint_context(complaint_id: str, agent_id: str = Query(...)):
    """
    Returns all AI analysis, the draft response, escalation reasoning, and
    suggested actions for the human agent to make an informed decision.

    Also transitions the complaint to in_review and starts the review timer.
    """
    try:
        context = prepare_review_context(complaint_id)
    except ValueError as exc:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail=str(exc))

    # Start review timer (non-blocking — ignore errors)
    try:
        track_review_started(complaint_id, agent_id)
    except Exception:
        pass

    return context


@router.post(
    "/complaint/{complaint_id}/action",
    summary="Submit agent action: ACCEPT / EDIT / REJECT / MANUAL_ESCALATE",
)
def submit_agent_action(complaint_id: str, body: AgentActionRequest):
    """
    Process the human agent's review decision.

    ACCEPT          → sends AI draft to customer, closes complaint.
    EDIT            → sends edited response, closes complaint.
    REJECT          → discards AI draft, agent must write manually.
    MANUAL_ESCALATE → escalates to a higher tier, re-runs pipeline.
    """
    payload = {
        "edited_response":        body.edited_response,
        "rejection_reason":       body.rejection_reason,
        "escalation_target_tier": body.escalation_target_tier,
    }

    valid, error_msg = validate_action(complaint_id, body.agent_id, body.action, payload)
    if not valid:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    try:
        if body.action == "ACCEPT":
            result = handle_accept(complaint_id, body.agent_id, body.notes)

        elif body.action == "EDIT":
            result = handle_edit(
                complaint_id, body.agent_id,
                body.edited_response or "", body.notes,
            )

        elif body.action == "REJECT":
            result = handle_reject(
                complaint_id, body.agent_id,
                body.rejection_reason or "", body.notes,
            )

        elif body.action == "MANUAL_ESCALATE":
            result = handle_manual_escalate(
                complaint_id, body.agent_id,
                body.escalation_target_tier or 2,
                body.rejection_reason or "",
                body.notes,
            )

        return result

    except ValueError as exc:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Agent action failed complaint=%s action=%s", complaint_id, body.action)
        raise HTTPException(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Action failed: {exc}",
        )


@router.post(
    "/next-complaint",
    summary="Fetch and assign next highest-priority complaint to agent",
)
def fetch_next_complaint(body: NextComplaintRequest):
    """
    Pops the highest-priority QUEUED complaint for the agent's tier and assigns it.
    Returns the full review context so the agent can start immediately.
    """
    queue_row = get_next_complaint(body.agent_id, body.tier_level)
    if not queue_row:
        return {"message": "Queue is empty. No complaints waiting.", "complaint": None}

    complaint_id = queue_row["complaint_id"]
    try:
        context = prepare_review_context(complaint_id)
    except ValueError:
        context = {"complaint_id": complaint_id, "note": "Context unavailable"}

    track_review_started(complaint_id, body.agent_id)

    return {
        "message": "Complaint assigned.",
        "queue_info": {
            "assigned_to":   body.agent_id,
            "priority_score": queue_row.get("priority_score"),
            "sla_deadline":  queue_row.get("sla_deadline"),
        },
        "complaint": context,
    }


@router.get(
    "/metrics/{agent_id}",
    summary="Agent performance metrics",
)
def agent_metrics(
    agent_id: str,
    date_from: str | None = Query(None, description="ISO date string"),
    date_to:   str | None = Query(None, description="ISO date string"),
):
    return get_agent_metrics(agent_id, date_from, date_to)


@router.get(
    "/team-metrics/{tier_level}",
    summary="Team-level metrics for a tier",
)
def team_metrics(
    tier_level: int,
    date_from: str | None = Query(None),
    date_to:   str | None = Query(None),
):
    return get_team_metrics(tier_level, date_from, date_to)
