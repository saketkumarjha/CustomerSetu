"""
Pipeline execution and SSE streaming routes.

Two endpoints:
1. POST /run/{complaint_id}  — trigger pipeline for an existing complaint
2. GET  /stream/{complaint_id} — SSE stream of agent progress
3. GET  /debug/logs — tail last 200 lines of application.log (Azure only)
"""

import json
import logging
import asyncio
import os
import traceback
from fastapi import APIRouter, HTTPException, status, Request, Path
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
from app.services.signal_extractor import extract_and_store_signals
from app.services.cluster_builder import build_clusters
from app.services.duplicate_service import detect_cross_channel_duplicates

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
    logger.info("[PIPELINE] Starting pipeline for complaint_id=%s", complaint_id)

    try:
        await update_complaint_status(complaint_id, "processing")

        # Run the LangGraph graph — this executes all nodes in sequence
        # Each node publishes SSE events internally via event_bus
        logger.info("[PIPELINE] Invoking pipeline_graph for complaint_id=%s", complaint_id)
        try:
            final_state = await pipeline_graph.ainvoke(initial_state)
        except Exception as graph_exc:
            logger.exception("[PIPELINE] pipeline_graph.ainvoke raised an unhandled exception complaint_id=%s", complaint_id)
            raise

        # Persist all pipeline outputs to complaints table
        await _save_pipeline_outputs(complaint_id, final_state)

        # ── Signal Extraction Layer ───────────────────────────────────────────
        # Normalise pipeline outputs → complaint_signals row.
        # Must run AFTER _save_pipeline_outputs so the complaints FK exists.
        # customer_id is passed explicitly from initial_state because LangGraph
        # does not guarantee input-only fields survive into final_state.
        await extract_and_store_signals(
            complaint_id,
            final_state,
            customer_id=initial_state.get("customer_id"),
        )

        # ── Cluster Builder ───────────────────────────────────────────────────
        # Rebuild active clusters from the last 24 h of signals.
        # Runs inline here; a separate scheduler also fires every 5 min.
        # If this is slow in production, move to asyncio.create_task().
        await build_clusters()

        # ── Cross-channel duplicate detection ─────────────────────────────────
        try:
            detect_cross_channel_duplicates(complaint_id)
        except Exception as dedup_exc:
            logger.warning("[DEDUP] Detection failed for %s: %s", complaint_id, dedup_exc)

        # Build the final summary for the SSE stream and idempotency cache
        route = final_state.get("route")
        final_summary = {
            "complaint_id":     complaint_id,
            "status":           "complete",
            "route":            route,
            "category":         final_state.get("category"),
            "severity":         final_state.get("severity"),
            "confidence_score": final_state.get("confidence_score"),
            "is_rbi_reportable": final_state.get("is_rbi_reportable"),
            "sla_hours":        final_state.get("sla_hours"),
            "agent_count":      len(final_state.get("explanation_trace", [])),
        }

        # Append route-specific details
        orch_result = final_state.get("escalation_orchestrator_result") or {}

        if route == "AUTO":
            escalation_info = final_state.get("escalation_info") or {}
            final_summary.update({
                "tier_resolved":        final_state.get("current_tier", 1),
                "confidence":           final_state.get("confidence_score"),
                "response_sent":        bool(final_state.get("customer_notified_at")),
                "notification_channel": final_state.get("notification_channel"),
                "customer_notified_at": final_state.get("customer_notified_at"),
                "escalation_info": {
                    "next_tier":           escalation_info.get("next_tier"),
                    "escalation_deadline": escalation_info.get("escalation_deadline_iso"),
                },
            })

        elif orch_result.get("final_route") == "auto_respond":
            # Route 3 resolved with auto-respond at a higher tier
            final_summary.update({
                "route":                "escalation_auto_respond",
                "tier_resolved":        orch_result.get("final_tier"),
                "confidence":           orch_result.get("confidence_score"),
                "response_sent":        bool(orch_result.get("customer_notified_at")),
                "notification_channel": orch_result.get("notification_channel"),
                "customer_notified_at": orch_result.get("customer_notified_at"),
                "escalation_summary": {
                    "escalation_path":     orch_result.get("escalation_path", []),
                    "total_escalations":   orch_result.get("total_escalations", 0),
                    "stop_reason":         orch_result.get("stop_reason"),
                    "final_tier":          orch_result.get("final_tier"),
                },
            })

        elif orch_result.get("final_route") == "human_review" and orch_result.get("total_escalations", 0) > 0:
            # Route 3 ended at human review after escalation attempts
            final_summary.update({
                "route":      "escalation_human_review",
                "tier":       orch_result.get("final_tier"),
                "confidence": orch_result.get("confidence_score"),
                "escalation_summary": {
                    "escalation_path":   orch_result.get("escalation_path", []),
                    "total_escalations": orch_result.get("total_escalations", 0),
                    "stop_reason":       orch_result.get("stop_reason"),
                    "final_tier":        orch_result.get("final_tier"),
                },
            })

        elif final_state.get("escalation_decision") == "HUMAN_AT_CURRENT_TIER":
            # Fetch queue state written by routing_node
            from app.db.supabase_client import get_supabase
            supabase = get_supabase()
            q_result = (
                supabase.table("agent_queue")
                .select("assigned_to, queue_position, priority_score, sla_deadline, estimated_review_time, tier_level")
                .eq("complaint_id", complaint_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            q_row = q_result.data[0] if q_result.data else {}

            final_summary.update({
                "route":       "human_review",
                "tier":        final_state.get("assigned_tier") or final_state.get("current_tier", 1),
                "confidence":  final_state.get("confidence_score"),
                "escalation_not_triggered_reason": (
                    "No higher-tier signals detected — issue matches current tier scope"
                ),
                "assignment": {
                    "assigned_to":          q_row.get("assigned_to"),
                    "tier_level":           q_row.get("tier_level"),
                    "queue_position":       q_row.get("queue_position"),
                    "estimated_wait_time":  f"{q_row.get('estimated_review_time', 12)} min",
                    "sla_deadline":         q_row.get("sla_deadline"),
                },
                "draft_response": {
                    "text":           final_state.get("draft_response"),
                    "confidence":     final_state.get("confidence_score"),
                    "can_be_accepted": (final_state.get("confidence_score") or 0) >= 0.80,
                },
            })

        elif route == "HUMAN":
            # Direct HUMAN override (RBI/fraud/compliance rules fired) — routing_node
            # sent the complaint straight to a high tier without going through escalation.
            # The HUMAN_AT_CURRENT_TIER case above doesn't match here because
            # escalation_decision is None for plain override routing.
            from app.db.supabase_client import get_supabase
            supabase = get_supabase()
            q_result = (
                supabase.table("agent_queue")
                .select("assigned_to, queue_position, priority_score, sla_deadline, estimated_review_time, tier_level")
                .eq("complaint_id", complaint_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            q_row = q_result.data[0] if q_result.data else {}

            final_summary.update({
                "route":            "human_review",
                "tier":             final_state.get("assigned_tier") or final_state.get("current_tier", 4),
                "confidence":       final_state.get("confidence_score"),
                "override_triggered": True,
                "assignment": {
                    "assigned_to":         q_row.get("assigned_to"),
                    "tier_level":          q_row.get("tier_level"),
                    "queue_position":      q_row.get("queue_position"),
                    "estimated_wait_time": f"{q_row.get('estimated_review_time', 12)} min",
                    "sla_deadline":        q_row.get("sla_deadline"),
                },
                "draft_response": {
                    "text":            final_state.get("draft_response"),
                    "confidence":      final_state.get("confidence_score"),
                    "can_be_accepted": (final_state.get("confidence_score") or 0) >= 0.80,
                },
            })

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

    # Map route → customer-facing status
    route = state.get("route", "")
    if route == "AUTO":
        customer_status = "auto_closed"
    elif route in ("HUMAN", "human_review"):
        customer_status = "human_review"
    elif route in ("ESCALATE", "escalate"):
        customer_status = "escalated"
    else:
        customer_status = "complete"

    update_data = {
        # ── PII / text ────────────────────────────────────────────────────────
        "masked_text":              state.get("masked_text"),
        "language":                 state.get("language"),
        # ── Duplicate detection ───────────────────────────────────────────────
        "is_duplicate":             state.get("is_duplicate", False),
        # duplicate_of (uuid[]) is owned by duplicate_service.py — not written here
        # ── Classification ────────────────────────────────────────────────────
        "category":                 state.get("category"),
        "category_confidence":      state.get("category_confidence"),
        # ── Sentiment / urgency ───────────────────────────────────────────────
        "sentiment":                state.get("sentiment"),
        "urgency_score":            state.get("urgency_score"),
        "escalation_flag":          state.get("escalation_flag", False),
        # ── Compliance ────────────────────────────────────────────────────────
        "compliance_category":      state.get("compliance_category"),
        "is_rbi_reportable":        state.get("is_rbi_reportable", False),
        "rbi_reportable":           state.get("is_rbi_reportable", False),  # DB column alias
        # ── Severity ─────────────────────────────────────────────────────────
        "severity":                 state.get("severity"),
        "severity_score":           state.get("severity_score"),
        "severity_breakdown":       state.get("severity_breakdown"),
        # ── Resolution ───────────────────────────────────────────────────────
        "draft_response":           state.get("draft_response"),
        "root_cause":               state.get("root_cause"),
        "action_steps":             state.get("action_steps", []),
        # ── Confidence / grounding ────────────────────────────────────────────
        "confidence_score":         state.get("confidence_score"),
        "grounding_score":          state.get("grounding_score"),
        "grounding_warnings":       state.get("grounding_warnings", []),
        # ── Routing ───────────────────────────────────────────────────────────
        "route":                    state.get("route"),
        "risk_score":               state.get("risk_score"),
        "sla_hours":                state.get("sla_hours"),
        "rbi_tat_deadline":         state.get("rbi_tat_deadline"),
        # ── Pipeline / customer-facing status ─────────────────────────────────
        "pipeline_status":          "complete",
        "status":                   customer_status,   # never set to "AUTO"/"ESCALATE" etc.
        # ── Tier fields ───────────────────────────────────────────────────────
        # After the pipeline finishes, current_tier must equal the final resolved
        # tier (assigned_tier).  Using "or" chains is unsafe when tier values can
        # be 0 (falsy), so we use explicit None guards.
        "assigned_tier":            max((state.get("assigned_tier") or state.get("current_tier") or 1), 1),
        "current_tier":             max((state.get("assigned_tier") or state.get("current_tier") or 1), 1),
        # tier_level is NOT a DB column — removed to prevent silent update failure
        "tier_scope":               state.get("tier_scope"),
        "tier_kb_coverage_score":   state.get("tier_kb_coverage_score"),
        "missing_info_indicators":  state.get("missing_info_indicators") or [],
        "resolution_type":          state.get("resolution_type"),
        "authority_sufficient":     state.get("authority_sufficient"),
        # ── Auto-response tracking ────────────────────────────────────────────
        "final_response_text":      state.get("formatted_response"),
        "response_sent_at":         state.get("customer_notified_at"),
        "auto_sent_at":             state.get("customer_notified_at"),
        "response_channel":         state.get("notification_channel"),
        "tier_resolved_at":         state.get("current_tier"),  # INTEGER — tier number, not timestamp
        # ── Escalation tracking ───────────────────────────────────────────────
        "escalation_count":         state.get("escalation_count", 0),
        "escalation_path":          state.get("escalation_path", []),
        "max_tier_reached":         max(
                                        state.get("max_tier_reached") or 0,
                                        state.get("current_tier") or 0,
                                    ),
        "total_escalations_count":  state.get("escalation_count", 0),
        "is_escalating":            False,   # always clear — pipeline is done
        "escalation_loop_detected": state.get("escalation_loop_detected", False),
        # ── RAG context ───────────────────────────────────────────────────────
        "context_documents":        state.get("context_documents", []),
    }

    try:
        result = supabase.table("complaints").update(update_data).eq(
            "complaint_id", complaint_id
        ).execute()
        if not result.data:
            logger.warning("[PIPELINE] _save_pipeline_outputs: UPDATE returned no rows for %s — row may not exist", complaint_id)
        else:
            logger.info("[PIPELINE] Saved pipeline outputs for %s (route=%s)", complaint_id, update_data.get("route"))
    except Exception as e:
        logger.exception("[PIPELINE] Failed to save outputs for %s: %s", complaint_id, e)


@router.post(
    "/run/{complaint_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger pipeline for a complaint",
    responses={404: {"description": "Complaint not found"}},
)
async def trigger_pipeline(
    complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)"),
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
        "context_documents": [],
        "draft_response": None,
        "root_cause": None,
        "action_steps": [],
        "confidence_score": None,
        "authority_sufficient": None,
        "grounding_score": None,
        "grounding_warnings": [],
        "route": None,
        "risk_score": None,
        "sla_hours": None,
        "rbi_tat_deadline": None,
        "routing_reason": None,
        # current_tier may be 0 in DB (standard route fast-track result).
        # Pipeline must use >= 1 so queue lookups land at a real tier.
        "current_tier": max(complaint.get("current_tier") or 1, 1),
        "assigned_tier": None,
        "escalation_decision": None,

        # Accumulating lists — start empty
        "explanation_trace": [],
        "errors": [],

        "pipeline_status": "started",
        "current_agent": None,

        # Auto-response tracking — populated by routing_node when route == "AUTO"
        "formatted_response":    None,
        "notification_channel":  None,
        "customer_notified_at":  None,
        "escalation_info":       None,

        # Route 3 escalation tracking — populated by escalation_orchestrator
        "escalation_count":               complaint.get("escalation_count", 0),
        "escalation_path":                complaint.get("escalation_path", []),
        "is_escalating":                  False,
        "escalation_orchestrator_result": None,

        # Tier-aware fields
        "tier_level":               max(complaint.get("current_tier") or 1, 1),
        "tier_scope":               complaint.get("tier_scope"),
        "tier_contact_info":        None,
        "previous_tier_attempts":   None,
        "tier_kb_coverage_score":   None,
        "missing_info_indicators":  None,
        "resolution_type":          None,
    }

    # Start pipeline in background — does not block this response.
    # Use asyncio.create_task instead of BackgroundTasks so that any
    # exception that escapes run_pipeline's own try/except is still logged
    # (BackgroundTasks silently discards unhandled exceptions).
    task = asyncio.create_task(run_pipeline(initial_state))

    def _log_task_exception(t: asyncio.Task) -> None:
        exc = t.exception() if not t.cancelled() else None
        if exc:
            logger.exception(
                "[PIPELINE] Background task raised unhandled exception complaint_id=%s",
                complaint_id,
                exc_info=exc,
            )

    task.add_done_callback(_log_task_exception)

    return {
        "message": "Pipeline started.",
        "complaint_id": complaint_id,
        "stream_url": f"/api/v1/pipeline/stream/{complaint_id}",
    }


@router.get(
    "/stream/{complaint_id}",
    summary="SSE stream — real-time pipeline agent updates",
    response_class=EventSourceResponse,
    include_in_schema=False,  # SSE streams can't be tested by REST schema validators
)
async def stream_pipeline(
    request: Request,
    complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)"),
):
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

            event_type = event.get("event", "agent_update")
            logger.info("[SSE] emit complaint_id=%s event=%s", complaint_id, event_type)

            # Build payload without the 'event' key (it becomes the SSE event type field).
            # Use dict comprehension instead of pop() to avoid mutating the shared dict.
            payload = {k: v for k, v in event.items() if k != "event"}
            yield {
                "event": event_type,
                "data": json.dumps(payload)
            }

        # Stream ended
        logger.info("[SSE] stream ended complaint_id=%s", complaint_id)
        yield {
            "event": "stream_closed",
            "data": json.dumps({"message": "Pipeline stream closed."})
        }

    return EventSourceResponse(event_generator())


@router.get(
    "/debug/logs",
    summary="Tail last N lines of application.log (Azure debug only)",
    include_in_schema=False,
)
async def debug_logs(lines: int = 200):
    """
    Returns the last N lines of the application log file.
    Checks /home/LogFiles/application.log first, then /tmp/application.log.
    """ 
    for log_path in ("/home/LogFiles/application.log", "/tmp/application.log"):
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                tail = all_lines[-lines:]
                return {
                    "log_path": log_path,
                    "total_lines": len(all_lines),
                    "returned_lines": len(tail),
                    "content": "".join(tail),
                }
            except Exception as e:
                return {"error": str(e), "traceback": traceback.format_exc()}

    return {
        "error": "Log file not found in /home/LogFiles or /tmp",
        "hint": "Trigger a pipeline run first, then check again.",
        "cwd": os.getcwd(),
        "tmp_contents": os.listdir("/tmp") if os.path.isdir("/tmp") else "missing",
        "home_exists": os.path.isdir("/home"),
        "home_logfiles_exists": os.path.isdir("/home/LogFiles"),
    }


@router.get(
    "/debug/openai-test",
    summary="Test OpenAI API connectivity from the container (Azure debug only)",
    include_in_schema=False,
)
async def debug_openai_test():
    """
    Makes a minimal GPT-4o call and returns the result or full error.
    Use this to confirm the OpenAI API key and region are working.
    """
    import time
    from app.core.config import get_settings

    settings = get_settings()
    key_preview = f"{settings.openai_api_key[:12]}...{settings.openai_api_key[-4:]}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=0)
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=5,
            temperature=0,
        )
        elapsed = round((time.perf_counter() - t0) * 1000)
        return {
            "status": "success",
            "api_key_preview": key_preview,
            "response": response.choices[0].message.content,
            "latency_ms": elapsed,
            "model": response.model,
        }
    except Exception as e:
        logger.error("[DEBUG] OpenAI test failed: %s\n%s", e, traceback.format_exc())
        return {
            "status": "failed",
            "api_key_preview": key_preview,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
