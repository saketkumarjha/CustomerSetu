"""
Escalation Orchestrator

Entry point for Route 3 — Auto-Escalation.

Called from routing_node (graph.py) when Agent 10.5 returns decision == "ESCALATE".

Full flow:
  validate → loop-detect → log → SSE event → partial pipeline →
  stop-check → (auto_respond | escalate further | human_review)

Recursive depth is bounded by max_escalation_iterations (default 5).
"""

import asyncio
import json
from datetime import datetime, timezone

from app.utils.tier_transition_validator import validate_transition
from app.utils.escalation_stop_checker import should_stop_escalating
from app.utils.escalation_loop_detector import detect_loop
from app.utils.escalation_cache import mark_just_escalated, clear_complaint_cache
from app.services.escalation_logger import (
    log_escalation,
    mark_escalation_complete,
    mark_escalation_failed,
    update_escalation_result,
)
from app.services.escalation_rollback import rollback_escalation
from app.services.escalation_metrics import track_escalation_event
from app.services.partial_pipeline_runner import run_tier_transition_pipeline
from app.services.supervisor.event_bus import event_bus
from app.services.agents.esclation_analyzer import TIER_META
from app.db.supabase_client import get_supabase
from app.core.config import get_settings


async def execute_escalation(
    complaint_id: str,
    from_tier: int,
    to_tier: int,
    escalation_reason: str,
    original_state: dict,
    signals_detected: list = None,
    escalation_reasoning: str = "",
    depth: int = 0,
) -> dict:
    """
    Execute one escalation hop (from_tier → to_tier), then recurse if needed.

    Returns a final result dict with:
      final_route          : "auto_respond" | "human_review"
      final_tier           : int
      stop_reason          : str
      draft_response       : str
      confidence_score     : float
      escalation_path      : list[int]
      total_escalations    : int
      formatted_response   : str | None   (auto_respond only)
      customer_notified_at : str | None   (auto_respond only)
      notification_channel : str | None   (auto_respond only)
    """
    settings = get_settings()

    # Hard depth guard (independent of DB counter)
    if depth >= settings.max_escalation_iterations:
        return _human_result(
            from_tier, original_state, "MAX_ITERATIONS_REACHED",
            escalation_path=original_state.get("escalation_path", []),
        )

    # ── 1. Validate transition ────────────────────────────────────────────────
    validation = validate_transition(from_tier, to_tier, escalation_reason)
    if not validation["is_valid"]:
        return _human_result(
            from_tier, original_state, "INVALID_TRANSITION",
            escalation_path=original_state.get("escalation_path", []),
        )

    # ── 2. Read current DB state ──────────────────────────────────────────────
    supabase = get_supabase()
    db_row = _fetch_complaint_row(supabase, complaint_id)

    escalation_count = db_row.get("escalation_count") or 0
    escalation_path = _parse_path(db_row.get("escalation_path"))
    loop_already = db_row.get("escalation_loop_detected", False)
    last_escalation_at = db_row.get("last_escalation_at")

    # ── 3. Loop detection ─────────────────────────────────────────────────────
    projected_path = escalation_path + [to_tier]
    loop_check = detect_loop(complaint_id, projected_path, last_escalation_at, escalation_count)

    if loop_check["loop_detected"] or loop_already:
        supabase.table("complaints").update({
            "escalation_loop_detected": True,
            "is_escalating": False,
        }).eq("complaint_id", complaint_id).execute()
        track_escalation_event(complaint_id, "LOOP_DETECTED", {"reason": loop_check["loop_reason"]})
        return _human_result(
            from_tier, original_state, "LOOP_DETECTED", escalation_path=escalation_path
        )

    # ── 4. Max iterations check ───────────────────────────────────────────────
    if escalation_count >= settings.max_escalation_iterations:
        track_escalation_event(complaint_id, "MAX_ITERATIONS", {"count": escalation_count})
        return _human_result(
            from_tier, original_state, "MAX_ITERATIONS_REACHED", escalation_path=escalation_path
        )

    # ── 5. SSE: escalation_triggered ─────────────────────────────────────────
    await event_bus.publish(complaint_id, {
        "event": "escalation_triggered",
        "from_tier": from_tier,
        "to_tier": to_tier,
        "reason": escalation_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    if depth == 0:
        track_escalation_event(complaint_id, "ESCALATION_STARTED", {
            "from_tier": from_tier, "to_tier": to_tier
        })

    # ── 6. Log to DB + update complaint counters ──────────────────────────────
    log_result = log_escalation(
        complaint_id=complaint_id,
        from_tier=from_tier,
        to_tier=to_tier,
        escalation_reason=escalation_reason,
        confidence_before=original_state.get("confidence_score"),
        kb_coverage_before=original_state.get("tier_kb_coverage_score"),
        tier_response_text=original_state.get("draft_response", ""),
        signals_detected=signals_detected or [],
        escalation_decision_reasoning=escalation_reasoning,
    )
    escalation_count = log_result.get("escalation_count", escalation_count + 1)
    escalation_path = log_result.get("escalation_path", projected_path)
    history_id = log_result.get("history_id")

    # Mark complaint as actively escalating in DB so the frontend shows the
    # correct status while the partial pipeline runs at the new tier
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("complaints").update({
        "is_escalating":        True,
        "last_escalation_at":   now_iso,
        "escalation_count":     escalation_count,
        "escalation_path":      escalation_path,
        "max_tier_reached":     max(db_row.get("max_tier_reached") or 0, to_tier),
        "total_escalations_count": escalation_count,
        "current_tier":         to_tier,
        "assigned_tier":        to_tier,
        "status":               "escalated",
    }).eq("complaint_id", complaint_id).execute()

    # Anti-rapid-fire cache
    mark_just_escalated(complaint_id, to_tier)

    # ── 7. SSE: tier_transition ───────────────────────────────────────────────
    tier_info = TIER_META.get(to_tier, {"label": f"Tier {to_tier}"})
    await event_bus.publish(complaint_id, {
        "event": "tier_transition",
        "entering_tier": to_tier,
        "tier_name": tier_info["label"],
        "re_running_agents": [7, 8, 9, 10, "10.5"],
    })

    # ── 8. Partial pipeline at new tier ──────────────────────────────────────
    try:
        pipeline_result = await run_tier_transition_pipeline(
            complaint_id=complaint_id,
            new_tier_level=to_tier,
            original_state={
                **original_state,
                "current_tier": to_tier,
                "escalation_count": escalation_count,
                "escalation_path": escalation_path,
            },
            from_tier=from_tier,
        )
    except Exception as exc:
        update_escalation_result(history_id, status="failed")
        rollback_escalation(complaint_id, from_tier, str(exc))
        track_escalation_event(complaint_id, "ESCALATION_FAILED", {"error": str(exc)})
        return _human_result(
            from_tier, original_state, "PIPELINE_FAILED", escalation_path=escalation_path
        )

    # Write pipeline outputs back to the history row (phase-2 write)
    update_escalation_result(
        history_id=history_id,
        tier_response_text=pipeline_result.get("draft_response"),
        tier_knowledge_used=[
            {"id": doc.get("id"), "category": doc.get("category"), "similarity": doc.get("similarity")}
            for doc in pipeline_result.get("context_documents", [])
            if doc.get("id")
        ] or None,
        agent_outputs_snapshot={
            "route": pipeline_result.get("route"),
            "confidence_score": pipeline_result.get("confidence_score"),
            "grounding_score": pipeline_result.get("grounding_score"),
            "rag_coverage": pipeline_result.get("rag_coverage"),
            "escalation_decision": pipeline_result.get("escalation_decision"),
            "next_target_tier": pipeline_result.get("next_target_tier"),
            "errors": pipeline_result.get("errors", []),
        },
        status="completed",
    )

    new_confidence = pipeline_result.get("confidence_score", 0.5)
    new_route = pipeline_result.get("route", "ESCALATE")
    new_draft = pipeline_result.get("draft_response", "")
    esc_decision = pipeline_result.get("escalation_decision")
    next_target = pipeline_result.get("next_target_tier")

    # ── 9. SSE: per-agent updates for the partial run ─────────────────────────
    await event_bus.publish(complaint_id, {
        "event": "agent_update",
        "agent": f"Partial Pipeline (Tier {to_tier})",
        "tier": to_tier,
        "status": "completed",
        "confidence": new_confidence,
        "output_summary": (
            f"RAG: {len(pipeline_result.get('context_documents', []))} docs | "
            f"Confidence: {new_confidence:.1%} | "
            f"Route: {new_route}"
        ),
    })

    # ── 10. Stop-condition check ──────────────────────────────────────────────
    stop = should_stop_escalating(
        complaint_id=complaint_id,
        current_tier=to_tier,
        confidence=new_confidence,
        escalation_count=escalation_count,
        escalation_decision=esc_decision,
        loop_detected=False,
    )

    # ── 10a. AUTO_RESPOND ─────────────────────────────────────────────────────
    if stop["final_action"] == "auto_respond" or new_route == "AUTO":
        mark_escalation_complete(complaint_id, to_tier, "auto_respond")
        clear_complaint_cache(complaint_id)
        track_escalation_event(complaint_id, "ESCALATION_RESOLVED", {
            "final_tier": to_tier,
            "confidence": new_confidence,
            "escalation_count": escalation_count,
        })

        await event_bus.publish(complaint_id, {
            "event": "escalation_resolved",
            "final_tier": to_tier,
            "final_route": "auto_respond",
            "total_escalations": escalation_count,
            "escalation_path": escalation_path,
            "confidence": new_confidence,
        })

        # Execute auto-response at the resolved tier
        auto_result: dict = {}
        try:
            from app.services.auto_responder import execute_auto_response
            from app.tasks.kb_enrichment import schedule_kb_enrichment

            auto_result = await asyncio.to_thread(
                execute_auto_response,
                complaint_id=complaint_id,
                customer_id=original_state.get("customer_id", ""),
                channel=original_state.get("channel", "web"),
                draft_response=new_draft,
                tier="full_auto",
                confidence_score=new_confidence,
                tier_level=to_tier,
                sla_deadline=original_state.get("rbi_tat_deadline"),
            )

            asyncio.ensure_future(
                schedule_kb_enrichment(
                    complaint_id=complaint_id,
                    draft_response=new_draft,
                    confidence_score=new_confidence,
                    tier_level=to_tier,
                )
            )

            await event_bus.publish(complaint_id, {
                "event": "response_sent",
                "tier": to_tier,
                "confidence": new_confidence,
                "notification_channel": auto_result.get("notification_channel"),
                "sent_at": auto_result.get("customer_notified_at"),
                "escalation_path": escalation_path,
                "preview": new_draft[:150],
            })
        except Exception as exc:
            auto_result = {"error": str(exc)}

        return {
            "final_route": "auto_respond",
            "final_tier": to_tier,
            "stop_reason": "CONFIDENCE_MET",
            "draft_response": new_draft,
            "confidence_score": new_confidence,
            "escalation_path": escalation_path,
            "total_escalations": escalation_count,
            "formatted_response": auto_result.get("formatted_response"),
            "customer_notified_at": auto_result.get("customer_notified_at"),
            "notification_channel": auto_result.get("notification_channel"),
            "pipeline_result": pipeline_result,
        }

    # ── 10b. HUMAN_REVIEW via stop-condition ──────────────────────────────────
    if stop["should_stop"]:
        mark_escalation_complete(complaint_id, to_tier, "human_review")
        clear_complaint_cache(complaint_id)

        if stop["stop_reason"] == "MAX_TIER_REACHED":
            track_escalation_event(complaint_id, "MAX_TIER_REACHED", {"tier": to_tier})

        await event_bus.publish(complaint_id, {
            "event": "escalation_stopped",
            "reason": stop["stop_reason"],
            "final_tier": to_tier,
        })

        return {
            "final_route": "human_review",
            "final_tier": to_tier,
            "stop_reason": stop["stop_reason"],
            "draft_response": new_draft,
            "confidence_score": new_confidence,
            "escalation_path": escalation_path,
            "total_escalations": escalation_count,
            "pipeline_result": pipeline_result,
        }

    # ── 10c. ESCALATE further — recursive call ────────────────────────────────
    if esc_decision == "ESCALATE" and next_target and next_target > to_tier:
        first_signal = (
            pipeline_result["escalation_signals"][0]
            if pipeline_result.get("escalation_signals")
            else "CONFIDENCE_LOW"
        )
        return await execute_escalation(
            complaint_id=complaint_id,
            from_tier=to_tier,
            to_tier=next_target,
            escalation_reason=first_signal,
            original_state={
                **original_state,
                "draft_response": new_draft,
                "confidence_score": new_confidence,
                "current_tier": to_tier,
                "context_documents": pipeline_result.get("context_documents", []),
                "grounding_score": pipeline_result.get("grounding_score"),
                "grounding_warnings": pipeline_result.get("grounding_warnings", []),
                "tier_kb_coverage_score": pipeline_result.get("rag_coverage", 0.0),
                "escalation_path": escalation_path,
            },
            signals_detected=pipeline_result.get("escalation_signals", []),
            escalation_reasoning=pipeline_result.get("escalation_reasoning", ""),
            depth=depth + 1,
        )

    # ── Fallback: human review at current tier ────────────────────────────────
    mark_escalation_complete(complaint_id, to_tier, "human_review")
    clear_complaint_cache(complaint_id)

    return {
        "final_route": "human_review",
        "final_tier": to_tier,
        "stop_reason": "NO_FURTHER_ESCALATION",
        "draft_response": new_draft,
        "confidence_score": new_confidence,
        "escalation_path": escalation_path,
        "total_escalations": escalation_count,
        "pipeline_result": pipeline_result,
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _fetch_complaint_row(supabase, complaint_id: str) -> dict:
    result = (
        supabase.table("complaints")
        .select(
            "escalation_count, escalation_path, max_tier_reached, "
            "is_escalating, escalation_loop_detected, last_escalation_at"
        )
        .eq("complaint_id", complaint_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def _parse_path(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return []
    return []


def _human_result(tier: int, state: dict, stop_reason: str, escalation_path: list) -> dict:
    return {
        "final_route": "human_review",
        "final_tier": tier,
        "stop_reason": stop_reason,
        "draft_response": state.get("draft_response", ""),
        "confidence_score": state.get("confidence_score", 0.5),
        "escalation_path": escalation_path,
        "total_escalations": state.get("escalation_count") or len(escalation_path),
    }
