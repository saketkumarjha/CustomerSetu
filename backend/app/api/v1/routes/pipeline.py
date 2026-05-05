"""
Pipeline execution and SSE streaming routes.

Two endpoints:
1. POST /run/{complaint_id}  — trigger pipeline for an existing complaint
2. GET  /stream/{complaint_id} — SSE stream of agent progress
"""

import json
import logging
import asyncio
from fastapi import APIRouter, HTTPException, status, Request, BackgroundTasks
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

from app.services.supervisor.graph import pipeline_graph
from app.services.supervisor.event_bus import event_bus
from app.services.supervisor.pipeline_state import PipelineState
from app.services.supervisor.audit_trail import (
    update_complaint_status,
)
from app.middleware.idempotency import cache_idempotency_response
from app.db.supabase_client import get_supabase

router = APIRouter()


async def run_pipeline(initial_state: PipelineState) -> None:
    """
    Execute the full LangGraph pipeline for a complaint.
    Runs as a FastAPI BackgroundTask — does NOT block the HTTP response.

    After completion:
    - Updates complaint record in Supabase with all outputs
    - Sends final SSE event to close the stream
    - Caches response in idempotency table
    """
    complaint_id = initial_state["complaint_id"]

    try:
        await update_complaint_status(complaint_id, "processing")

        # Run the LangGraph graph — this executes all nodes in sequence
        # Each node publishes SSE events internally via event_bus
        final_state = await pipeline_graph.ainvoke(initial_state)

        # Persist all pipeline outputs to complaints table
        await _save_pipeline_outputs(complaint_id, final_state)

        # Build the final summary for the SSE stream and idempotency cache
        final_summary = {
            "complaint_id": complaint_id,
            "status": "complete",
            "route": final_state.get("route"),
            "category": final_state.get("category"),
            "severity": final_state.get("severity"),
            "confidence_score": final_state.get("confidence_score"),
            "is_rbi_reportable": final_state.get("is_rbi_reportable"),
            "sla_hours": final_state.get("sla_hours"),
            "agent_count": len(final_state.get("explanation_trace", [])),
        }

        # Send pipeline_complete event before closing stream
        await event_bus.publish(complaint_id, {
            "event": "pipeline_complete",
            **final_summary,
        })

        # Cache for idempotency
        if initial_state.get("idempotency_key"):
            await cache_idempotency_response(
                initial_state["idempotency_key"],
                final_summary
            )

    except Exception as e:
        error_msg = f"Pipeline failed: {str(e)}"
        logger.exception("Pipeline run failed complaint_id=%s", complaint_id)

        await update_complaint_status(complaint_id, "failed")
        await event_bus.publish(complaint_id, {
            "event": "pipeline_error",
            "complaint_id": complaint_id,
            "error": error_msg,
        })

    finally:
        # Always close the SSE stream
        await event_bus.close(complaint_id)


async def _save_pipeline_outputs(complaint_id: str, state: PipelineState) -> None:
    """Save all agent outputs from final state to complaints table."""
    supabase = get_supabase()

    update_data = {
        "masked_text": state.get("masked_text"),
        "language": state.get("language"),
        "is_duplicate": state.get("is_duplicate", False),
        "duplicate_of": state.get("duplicate_of"),
        "category": state.get("category"),
        "sentiment": state.get("sentiment"),
        "urgency_score": state.get("urgency_score"),
        "compliance_category": state.get("compliance_category"),
        "is_rbi_reportable": state.get("is_rbi_reportable", False),
        "severity": state.get("severity"),
        "severity_score": state.get("severity_score"),
        "draft_response": state.get("draft_response"),
        "root_cause": state.get("root_cause"),
        "action_steps": state.get("action_steps", []),
        "confidence_score": state.get("confidence_score"),
        "grounding_score": state.get("grounding_score"),
        "grounding_warnings": state.get("grounding_warnings", []),
        "route": state.get("route"),
        "risk_score": state.get("risk_score"),
        "sla_hours": state.get("sla_hours"),
        "rbi_tat_deadline": state.get("rbi_tat_deadline"),
        "pipeline_status": "complete",
        "status": state.get("route", "complete"),
    }

    try:
        supabase.table("complaints").update(update_data).eq(
            "complaint_id", complaint_id
        ).execute()
    except Exception as e:
        print(f"[PIPELINE] Failed to save outputs: {e}")


@router.post(
    "/run/{complaint_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger pipeline for a complaint",
)
async def trigger_pipeline(
    complaint_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Fetch complaint from Supabase and start the LangGraph pipeline.
    Returns immediately with 202 — pipeline runs in background.
    Frontend should connect to /stream/{complaint_id} for live updates.
    """
    supabase = get_supabase()

    # Fetch complaint record
    result = (
        supabase.table("complaints")
        .select("*")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint {complaint_id} not found."
        )

    complaint = result.data[0]
    # ── Pipeline guard — only block if genuinely running right now ────────
    # "complete" status does NOT block re-runs: the UI says "click Run to re-analyse".
    # "processing" only blocks if an active event_bus queue exists — a stale
    # "processing" status left by a crashed/restarted server is treated as restartable.
    current_status = complaint.get("pipeline_status")
    if current_status == "processing" and event_bus.has_queue(complaint_id):
        return {
            "message": "Pipeline is currently running for this complaint.",
            "complaint_id": complaint_id,
            "current_status": "processing",
            "stream_url": f"/api/v1/pipeline/stream/{complaint_id}",
            "hint": "Connect to stream URL to see live updates.",
        }

    # Create SSE queue before starting background task
    # Queue must exist before frontend connects to /stream
    event_bus.create_queue(complaint_id)

    # Build initial pipeline state from complaint record
    initial_state: PipelineState = {
        "complaint_id": complaint_id,
        "customer_id": complaint.get("customer_id", ""),
        "channel": complaint.get("channel", ""),
        "complaint_text": complaint.get("original_text") or "",
        "merged_text": complaint.get("merged_text") or complaint.get("original_text") or "",
        "image_url": complaint.get("image_url"),
        "idempotency_key": None,

        # All agent outputs start as None
        "masked_text": None,
        "language": None,
        "pii_entities_found": None,
        "is_duplicate": None,
        "duplicate_of": None,
        "duplicate_similarity": None,
        "category": None,
        "category_confidence": None,
        "sentiment": None,
        "urgency_score": None,
        "escalation_flag": None,
        "compliance_category": None,
        "is_rbi_reportable": None,
        "rbi_supervisor_override": None,
        "severity": None,
        "severity_score": None,
        "severity_breakdown": None,
        "context_documents": None,
        "draft_response": None,
        "root_cause": None,
        "action_steps": None,
        "confidence_score": None,
        "grounding_score": None,
        "grounding_warnings": None,
        "route": None,
        "risk_score": None,
        "sla_hours": None,
        "rbi_tat_deadline": None,
        "routing_reason": None,

        # Accumulating lists — start empty
        "explanation_trace": [],
        "errors": [],

        "pipeline_status": "started",
        "current_agent": None,
    }

    # Start pipeline in background — does not block this response
    background_tasks.add_task(run_pipeline, initial_state)

    return {
        "message": "Pipeline started.",
        "complaint_id": complaint_id,
        "stream_url": f"/api/v1/pipeline/stream/{complaint_id}",
    }


@router.get(
    "/stream/{complaint_id}",
    summary="SSE stream — real-time pipeline agent updates",
)
async def stream_pipeline(request: Request, complaint_id: str):
    """
    Server-Sent Events stream for real-time pipeline updates.

    Frontend connects here immediately after POST /run/{complaint_id}.
    Each SSE message is one agent completing or the pipeline finishing.

    Frontend usage:
        const source = new EventSource('/api/v1/pipeline/stream/{id}');
        source.onmessage = (e) => updateAgentStep(JSON.parse(e.data));
        source.addEventListener('pipeline_complete', () => source.close());
    """
    async def event_generator():
        logger.info("[SSE] client connected complaint_id=%s", complaint_id)
        # Send initial connection confirmation
        yield {
            "event": "connected",
            "data": json.dumps({
                "complaint_id": complaint_id,
                "message": "Pipeline stream connected. Waiting for agent updates."
            })
        }

        # Stream events from the queue until pipeline completes
        async for event in event_bus.subscribe(complaint_id):
            if await request.is_disconnected():
                logger.info("[SSE] client disconnected complaint_id=%s", complaint_id)
                break

            et = event.get("event", "agent_update")
            logger.info("[SSE] emit complaint_id=%s event=%s", complaint_id, et)

            event_type = event.pop("event", "agent_update")
            yield {
                "event": event_type,
                "data": json.dumps(event)
            }

        # Stream ended
        logger.info("[SSE] stream ended complaint_id=%s", complaint_id)
        yield {
            "event": "stream_closed",
            "data": json.dumps({"message": "Pipeline stream closed."})
        }

    return EventSourceResponse(event_generator())