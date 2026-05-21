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
from fastapi import APIRouter, HTTPException, Query, Path, Body, status as http_status
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
from app.utils.postgrest_errors import is_missing_relation_error

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class AgentActionRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    action: Literal["ACCEPT", "EDIT", "REJECT", "MANUAL_ESCALATE"]
    edited_response: str | None = None
    rejection_reason: str | None = None
    escalation_target_tier: int | None = None
    notes: str = ""


class NextComplaintRequest(BaseModel):
    model_config = {"strict": True}
    agent_id: str
    tier_level: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/queue",
    summary="List complaints in the agent queue",
)
def get_queue(
    agent_id: str = Query(..., description="Requesting agent's ID"),
    tier_level: int = Query(..., ge=1, le=5, description="Tier to query (1–5)"),
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

    try:
        queue_result = (
            supabase.table("agent_queue")
            .select("*")
            .eq("tier_level", tier_level)
            .in_("status", statuses)
            .order("priority_score", desc=True)
            .execute()
        )
        rows = queue_result.data or []
    except Exception as exc:
        # Swallow transient socket errors and schema-cache misses — return empty queue
        # rather than crashing the agent desk with a 500.
        logger.warning("get_queue: transient error for tier %d: %s", tier_level, exc)
        rows = []

    complaint_ids = [r["complaint_id"] for r in rows]
    complaints_meta: dict = {}
    if complaint_ids:
        try:
            c_result = (
                supabase.table("complaints")
                .select("complaint_id, category, severity, urgency_score, rbi_tat_deadline, status")
                .in_("complaint_id", complaint_ids)
                .execute()
            )
            for c in c_result.data or []:
                complaints_meta[c["complaint_id"]] = c
        except Exception as exc:
            logger.warning("get_queue: complaints meta fetch failed: %s", exc)

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
    responses={404: {"description": "Complaint not found"}},
)
def get_complaint_context(
    complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)"),
    agent_id: str = Query(...),
):
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
    responses={
        400: {"description": "Invalid action payload (missing required fields)"},
        404: {"description": "Complaint not found"},
        409: {"description": "Complaint is not in an actionable state, or agent is not the assigned agent"},
        500: {"description": "Action handler failed (WhatsApp/email send or DB error)"},
    },
)
def submit_agent_action(
    complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)"),
    body: AgentActionRequest = Body(...),
):
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
        if "not found" in error_msg.lower():
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail=error_msg)
        if "is in status" in error_msg.lower() or "assigned to" in error_msg.lower():
            raise HTTPException(http_status.HTTP_409_CONFLICT, detail=error_msg)
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, detail=error_msg)

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
    try:
        return get_agent_metrics(agent_id, date_from, date_to)
    except Exception as exc:
        logger.warning("agent_metrics: transient error for %s: %s", agent_id, exc)
        return {
            "agent_id": agent_id,
            "total_reviewed": 0,
            "avg_review_time": "N/A",
            "acceptance_rate": None,
            "edit_rate": None,
            "rejection_rate": None,
            "escalation_rate": None,
            "current_workload": 0,
            "categories_handled": {},
        }


@router.get(
    "/team-metrics/{tier_level}",
    summary="Team-level metrics for a tier",
)
def team_metrics(
    tier_level: int = Path(..., ge=1, le=5, description="Tier level (1–5)"),
    date_from: str | None = Query(None),
    date_to:   str | None = Query(None),
):
    try:
        return get_team_metrics(tier_level, date_from, date_to)
    except Exception as exc:
        # Transient socket errors should not crash the UI — return empty metrics
        logger.warning("team_metrics: transient error for tier %d: %s", tier_level, exc)
        return {
            "tier_level": tier_level,
            "agent_count": 0,
            "total_reviewed": 0,
            "queue_size": 0,
            "agents": [],
        }


@router.post(
    "/recover-stuck-complaints",
    summary="Queue complaints stuck in human_review/in_review with no agent_queue row",
)
def recover_stuck_complaints(
    tier_level: int = Query(1, ge=1, le=5, description="Tier to recover complaints for (1–5)"),
):
    """
    One-shot data repair: finds complaints that completed the pipeline with a
    human-review route but were never inserted into agent_queue (tier_pending_at IS NULL).

    Safe to call multiple times — skips complaints already in the queue.
    Returns the count of complaints recovered.
    """
    from app.services.queue_service import assign_to_queue
    from app.utils.postgrest_errors import is_missing_relation_error

    supabase = get_supabase()

    # Find stuck complaints: pipeline done, needs human, not yet queued
    try:
        stuck_result = (
            supabase.table("complaints")
            .select(
                "complaint_id, category, severity, severity_score, "
                "urgency_score, rbi_tat_deadline, assigned_tier, current_tier"
            )
            .in_("status", ["in_review", "human_review", "pending_review"])
            .eq("pipeline_status", "complete")
            .is_("tier_pending_at", "null")
            .execute()
        )
        stuck = stuck_result.data or []
    except Exception as exc:
        if is_missing_relation_error(exc):
            return {"recovered": 0, "message": "agent_queue table not found"}
        logger.warning("recover_stuck: DB error fetching stuck complaints: %s", exc)
        return {"recovered": 0, "message": f"Temporary DB error — try again shortly: {exc}"}

    if not stuck:
        return {"recovered": 0, "message": "No stuck complaints found"}

    # Check which ones are already in the queue to avoid duplicates
    stuck_ids = [c["complaint_id"] for c in stuck]
    try:
        existing_result = (
            supabase.table("agent_queue")
            .select("complaint_id")
            .in_("complaint_id", stuck_ids)
            .execute()
        )
        already_queued = {r["complaint_id"] for r in (existing_result.data or [])}
    except Exception:
        already_queued = set()

    recovered = 0
    for c in stuck:
        cid = c["complaint_id"]
        if cid in already_queued:
            continue
        # Use explicit None-check: `or` treats 0 as falsy and falls to the wrong default.
        _at = c.get("assigned_tier")
        _ct = c.get("current_tier")
        tier = (_at if _at is not None else (_ct if _ct is not None else tier_level))
        tier = max(tier or 1, 1)
        try:
            assign_to_queue(
                complaint_id=cid,
                tier_level=tier,
                urgency_score=float(c.get("urgency_score") or 5.0),
                severity=int(c.get("severity") or 3),
                severity_score=float(c.get("severity_score") or 5.0),
                category=c.get("category") or "General Banking",
                sla_deadline=c.get("rbi_tat_deadline"),
            )
            recovered += 1
        except Exception as exc:
            logger.warning("recover_stuck: failed to queue %s: %s", cid, exc)

    return {
        "recovered": recovered,
        "total_stuck": len(stuck),
        "message": f"Queued {recovered} complaint(s) at tier {tier_level}",
    }
