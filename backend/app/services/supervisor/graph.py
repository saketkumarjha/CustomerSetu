"""
LangGraph Pipeline Graph — The Supervisor Orchestrator

This file defines the full multi-agent pipeline as a LangGraph StateGraph.
Each node corresponds to one agent in your architecture diagram.

Current state: SKELETON — all nodes are functional stubs that:
  1. Emit SSE events (so frontend works immediately)
  2. Write to audit trail
  3. Pass state through

In subsequent phases (3-9), each stub will be replaced with
real implementation WITHOUT changing the graph structure.
This is the key architectural principle — the graph wiring
never changes, only the node internals.
"""

import asyncio
import logging
import time
from typing import Literal
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

from app.services.supervisor.pipeline_state import PipelineState
from app.services.supervisor.event_bus import event_bus
from app.services.supervisor.audit_trail import (
    write_agent_decision,
    mark_agent_processing,
    update_complaint_status,
)
from app.models.agent_output import AgentOutput, AgentStatus
from app.services.agents.pii_agent import run_pii_detection, build_pii_reasoning
from app.services.agents.duplicate_agent import check_for_duplicate, store_embedding
from app.services.agents.fanout_agents import run_parallel_fanout
from app.core.config import get_settings
from app.services.agents.rag_agent import retrieve_context
from app.services.agents.resolution_agent import generate_tier_aware_resolution
from app.services.agents.grounding_agent import run_grounding_check
from app.services.agents.routing_agent import make_routing_decision
# ── Helper: emit SSE + write audit trail ─────────────────────────────────────

async def _agent_start(
    complaint_id: str,
    agent_name: str,
    agent_order: int
) -> float:
    """
    Called at the beginning of every agent node.
    Emits 'processing' SSE event.
    Returns start time for duration calculation.
    """
    await event_bus.publish(complaint_id, {
        "event": "agent_update",
        "agent": agent_name,
        "order": agent_order,
        "status": "processing",
    })
    await mark_agent_processing(complaint_id, agent_name, agent_order)
    return time.perf_counter()


async def _agent_complete(
    complaint_id: str,
    agent_output: AgentOutput,
    start_time: float
) -> None:
    """
    Called at the end of every agent node.
    Sets duration, emits 'complete' SSE event, writes audit trail.
    """
    agent_output.duration_ms = int((time.perf_counter() - start_time) * 1000)

    await event_bus.publish(complaint_id, {
        "event": "agent_update",
        "agent": agent_output.agent_name,
        "order": agent_output.agent_order,
        "status": agent_output.status.value,
        "decision": agent_output.decision,
        "confidence": agent_output.confidence,
        "reasoning": agent_output.reasoning,
        "duration_ms": agent_output.duration_ms,
    })

    await write_agent_decision(complaint_id, agent_output)


# ── NODE 1: PII Agent ─────────────────────────────────────────────────────────
# Add this import at the TOP of graph.py with other imports:
# from app.services.agents.pii_agent import run_pii_detection, build_pii_reasoning

async def pii_node(state: PipelineState) -> dict:
    """
    PHASE 3 — Real Presidio PII masking implementation.

    Replaces stub. Now runs full entity detection and masking.
    Output masked_text flows to ALL downstream nodes.
    """
    agent_name = "PII & Preprocessing Agent"
    agent_order = 1
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        # Run real Presidio detection on merged_text
        # merged_text = complaint text + image-extracted text (from image handler)
        pii_result = run_pii_detection(state["merged_text"])

        masked_text = pii_result["masked_text"]
        language = pii_result["language"]
        pii_entities = pii_result["pii_entities"]
        entity_summary = pii_result["entity_summary"]
        pii_detected = pii_result["pii_detected"]

        reasoning = build_pii_reasoning(pii_result)

        # Evidence: list of entity types found (not the values)
        evidence = list(entity_summary.keys())

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.COMPLETE,
            decision=(
                f"Language: {language.upper()} | "
                f"PII entities masked: {len(pii_entities)} | "
                f"Types: {', '.join(evidence) if evidence else 'None'}"
            ),
            confidence=0.99,
            reasoning=reasoning,
            evidence=evidence,
            metadata={
                "language": language,
                "entity_count": len(pii_entities),
                "entity_summary": entity_summary,
                "pii_detected": pii_detected,
                "original_text_length": len(state["merged_text"]),
                "masked_text_length": len(masked_text),
            },
        )

    except Exception as e:
        # PII failure is non-fatal — pass text through unmasked but log the error.
        # Reason: it is better to process an unmasked complaint with a warning
        # than to block the entire pipeline. The agent's error is visible in XAI.
        masked_text = state["merged_text"]
        language = "en"
        pii_entities = []
        evidence = []

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision="PII masking failed — text passed through unmasked",
            confidence=0.0,
            reasoning=f"Presidio error: {str(e)}. Text forwarded unmasked.",
            evidence=[],
            metadata={"error": str(e), "fallback": "unmasked_passthrough"},
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    return {
        "masked_text": masked_text,
        "language": language,
        "pii_entities_found": pii_entities,
        "current_agent": agent_name,
        "explanation_trace": [output.model_dump()],
        "errors": [str(output.error_message)] if output.error_message else [],
    }
async def duplicate_node(state: PipelineState) -> dict:
    """
    PHASE 4 — Real duplicate detection via OpenAI embeddings + pgvector.
    """
    agent_name = "Duplicate Detection Agent"
    agent_order = 2
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        settings = get_settings()
        threshold = settings.duplicate_threshold

        # Uses masked_text — PII removed so identical issues
        # from different customers match correctly
        result = await asyncio.to_thread(
            check_for_duplicate,
            complaint_id,
            state["masked_text"],
            threshold,
        )

        is_duplicate = result["is_duplicate"]
        duplicate_of = result["duplicate_of"]
        similarity = result["similarity_score"]
        reasoning = result["reasoning"]

        # Store embedding on complaint record (only if unique)
        if not is_duplicate and result["embedding"]:
            await asyncio.to_thread(
                store_embedding,
                complaint_id,
                result["embedding"],
            )

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.COMPLETE,
            decision=(
                f"DUPLICATE of {duplicate_of} "
                f"(similarity: {similarity:.1%})"
                if is_duplicate
                else f"UNIQUE — searched {result['total_searched']} complaints"
            ),
            confidence=similarity if is_duplicate else 1.0 - similarity,
            reasoning=reasoning,
           evidence=[
    f"Match: {m['complaint_id']} ({m['similarity']:.1%})"
    for m in result["all_matches"]
] if is_duplicate else [],
            metadata={
                "is_duplicate": is_duplicate,
                "duplicate_of": duplicate_of,
                "similarity_score": similarity,
                "threshold": threshold,
                "total_complaints_searched": result["total_searched"],
                "all_matches": result["all_matches"],
            },
        )

    except Exception as e:
        # If embedding/search fails, treat as unique and continue
        # Better to process a potential duplicate than block real complaints
        is_duplicate = False
        duplicate_of = None
        similarity = 0.0

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision="Detection failed — treated as UNIQUE (safe fallback)",
            confidence=0.0,
            reasoning=f"Duplicate detection error: {str(e)}. Proceeding as unique.",
            metadata={"error": str(e), "fallback": "treated_as_unique"},
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    return {
        "is_duplicate": is_duplicate,
        "duplicate_of": duplicate_of,
        "duplicate_similarity": similarity,
        "current_agent": agent_name,
        "explanation_trace": [output.model_dump()],
        "errors": [str(output.error_message)] if output.error_message else [],
    }
# ── CONDITIONAL EDGE: duplicate check ────────────────────────────────────────

def route_after_duplicate(
    state: PipelineState,
) -> Literal["parallel_fanout_node", "__end__"]:
    """
    If complaint is a duplicate → end pipeline immediately.
    No LLM spend on duplicates. This is the architectural win.
    """
    if state.get("is_duplicate"):
        return END
    return "parallel_fanout_node"


# ── NODE 3: Parallel Fan-out (4 agents simultaneously) ───────────────────────
async def parallel_fanout_node(state: PipelineState) -> dict:
    """
    PHASE 5 — Real parallel GPT-4o agents via asyncio.gather().
    All 4 agents run simultaneously.
    """
    complaint_id = state["complaint_id"]

    # Emit processing events for all 4 simultaneously
    for agent_name, order in [
        ("Classification Agent", 3),
        ("Sentiment Agent", 4),
        ("Compliance Agent", 5),
        ("Severity Agent", 6),
    ]:
        await event_bus.publish(complaint_id, {
            "event": "agent_update",
            "agent": agent_name,
            "order": order,
            "status": "processing",
        })
        await mark_agent_processing(complaint_id, agent_name, order)

    # Run all 4 agents in parallel
    # Uses masked_text from PII agent — safe for external API
    start = time.perf_counter()

    results = await run_parallel_fanout(state["masked_text"])

    total_duration = int((time.perf_counter() - start) * 1000)

    classification = results["classification"]
    sentiment = results["sentiment"]
    compliance = results["compliance"]
    severity = results["severity"]

    # Write all 4 to audit trail and emit completion events
    for output in [classification, sentiment, compliance, severity]:
        await write_agent_decision(complaint_id, output)
        await event_bus.publish(complaint_id, {
            "event": "agent_update",
            "agent": output.agent_name,
            "order": output.agent_order,
            "status": output.status.value,
            "decision": output.decision,
            "confidence": output.confidence,
            "duration_ms": output.duration_ms,
        })

    # Extract values from agent outputs
    cat_meta = classification.metadata or {}
    sent_meta = sentiment.metadata or {}
    comp_meta = compliance.metadata or {}
    sev_meta = severity.metadata or {}

    return {
        "category": cat_meta.get("category", "General Banking"),
        "category_confidence": classification.confidence,
        "sentiment": sent_meta.get("emotion", "Neutral"),
        "urgency_score": sent_meta.get("urgency_score", 5),
        "escalation_flag": sent_meta.get("escalation_flag", False),
        "compliance_category": comp_meta.get("rbi_category", "NOT_APPLICABLE"),
        "is_rbi_reportable": comp_meta.get("is_rbi_reportable", False),
        "rbi_supervisor_override": comp_meta.get("supervisor_override"),
        "severity": sev_meta.get("severity_level", 3),
        "severity_score": sev_meta.get("severity_score", 5.0),
        "severity_breakdown": sev_meta.get("scoring_breakdown", {}),
        "current_agent": "Parallel Fan-out Complete",
        "explanation_trace": [
            classification.model_dump(),
            sentiment.model_dump(),
            compliance.model_dump(),
            severity.model_dump(),
        ],
        "errors": [
            output.error_message
            for output in [classification, sentiment, compliance, severity]
            if output.error_message
        ],
    }

# ── NODE 4: RAG Memory Agent ──────────────────────────────────────────────────
async def rag_node(state: PipelineState) -> dict:
    """
    PHASE 6 — Real RAG retrieval via pgvector knowledge base.
    """
    agent_name = "Memory & RAG Agent"
    agent_order = 7
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        result = await asyncio.to_thread(
            retrieve_context,
            state["masked_text"],
            state.get("category", "General Banking"),
            3,
        )

        documents = result["documents"]
        reasoning = result["reasoning"]
        total_in_kb = result["total_in_kb"]

        # Build evidence list — source categories of retrieved docs
        evidence = [
            f"{doc.get('category', 'Unknown')} ({doc.get('similarity', 0):.1%})"
            for doc in documents
        ]

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.COMPLETE,
            decision=(
                f"Retrieved {len(documents)} context document(s) "
                f"from {total_in_kb} in knowledge base"
            ),
            confidence=1.0 if documents else 0.5,
            reasoning=reasoning,
            evidence=evidence,
            metadata={
                "document_count": len(documents),
                "total_in_kb": total_in_kb,
                "retrieval_method": result["retrieval_method"],
                "top_similarity": (
                    round(documents[0].get("similarity", 0), 4)
                    if documents else 0
                ),
            },
        )

    except Exception as e:
        documents = []
        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision="RAG retrieval failed — proceeding without context",
            confidence=0.0,
            reasoning=f"RAG error: {str(e)}. Resolution will proceed without context.",
            metadata={"error": str(e)},
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    return {
        "context_documents": documents,
        "current_agent": agent_name,
        "explanation_trace": [output.model_dump()],
        "errors": [str(output.error_message)] if output.error_message else [],
    }

# ── NODE 5: Resolution Agent ──────────────────────────────────────────────────
async def resolution_node(state: PipelineState) -> dict:
    """
    PHASE 8 — Tier-Aware Resolution Generator with dynamic few-shot prompting.
    """
    agent_name = "Resolution Generator"
    agent_order = 8
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        result = await asyncio.to_thread(
            generate_tier_aware_resolution,
            state.get("complaint_text", ""),
            state.get("masked_text", ""),
            state.get("category", "General Banking"),
            state.get("sentiment", "Neutral"),
            state.get("severity", 3),
            state.get("urgency_score", 5.0),
            state.get("compliance_category", "NOT_APPLICABLE"),
            state.get("is_rbi_reportable", False),
            state.get("language", "en"),
            state.get("context_documents", []),
            state.get("tier_level", None),
            state.get("tier_contact_info", None),
            state.get("previous_tier_attempts", None),
        )

        draft = result["draft_response"]
        root_cause = result["root_cause"]
        action_steps = result["action_steps"]
        confidence = result["confidence"]
        meets_threshold = result["meets_threshold"]
        never_auto = result["never_auto_respond"]
        category_threshold = result["category_threshold"]
        context_used = result["context_used"]
        resolution_type = result["resolution_type"]
        authority_sufficient = result["authority_sufficient"]

        reasoning = (
            f"Resolution generated using GPT-4o.\n"
            f"RAG context documents used: {context_used}\n"
            f"Confidence: {confidence:.1%}\n"
            f"Category threshold: {category_threshold:.0%}\n"
            f"Meets auto-respond threshold: {'YES' if meets_threshold else 'NO'}\n"
            + (f"⚠️ NEVER AUTO-RESPOND category — forced to human review\n"
               if never_auto else "")
            + f"Confidence reasoning: {result.get('confidence_reasoning', '')}\n"
            f"Root cause: {root_cause}\n"
            f"Resolution type: {resolution_type}\n"
            f"Authority sufficient: {authority_sufficient}"
        )

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.COMPLETE,
            decision=(
                f"Draft generated — confidence: {confidence:.1%} "
                f"({'✓ meets threshold' if meets_threshold else '✗ below threshold'})"
            ),
            confidence=confidence,
            reasoning=reasoning,
            evidence=[root_cause] if root_cause else [],
            metadata={
                "root_cause": root_cause,
                "action_step_count": len(action_steps),
                "context_documents_used": context_used,
                "confidence": confidence,
                "category_threshold": category_threshold,
                "meets_threshold": meets_threshold,
                "never_auto_respond": never_auto,
            },
        )

    except Exception as e:
        draft = (
            "We have received your complaint and our team is reviewing it. "
            "A representative will contact you within 24 hours."
        )
        root_cause = "Unable to determine — manual review required"
        action_steps = ["Review complaint manually", "Contact customer within 24 hours"]
        confidence = 0.3
        meets_threshold = False
        authority_sufficient = False

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision="Generation failed — fallback draft provided",
            confidence=confidence,
            reasoning=f"Resolution generation error: {str(e)}. Safe fallback draft used.",
            metadata={
                "error": str(e),
                "fallback": True,
                "meets_threshold": False,
            },
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    return {
        "draft_response": draft,
        "root_cause": root_cause,
        "action_steps": action_steps,
        "confidence_score": confidence,
        "authority_sufficient": authority_sufficient,
        "current_agent": agent_name,
        "explanation_trace": [output.model_dump()],
        "errors": [str(output.error_message)] if output.error_message else [],
    }

# ── NODE 6: Grounding Agent ───────────────────────────────────────────────────

async def grounding_node(state: PipelineState) -> dict:
    """
    PHASE 8 — Real LLM-as-judge grounding check on the resolution draft.
    """
    agent_name = "Grounding & Fact Check Agent"
    agent_order = 9
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        result = await asyncio.to_thread(
            run_grounding_check,
            state.get("draft_response", ""),
            state.get("complaint_text", ""),
            state.get("is_rbi_reportable", False),
            state.get("compliance_category", "NOT_APPLICABLE"),
        )

        grounding_score = result["grounding_score"]
        warnings = result["warnings"]
        overall = result["overall_assessment"]
        reasoning = result["reasoning"]

        # Build evidence list — the problematic claims found
        evidence = [
            f"[{w.get('type', '')}] {w.get('claim', '')[:60]}"
            for w in warnings[:4]
        ]

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.COMPLETE,
            decision=(
                f"Grounding score: {grounding_score:.0%} | "
                f"{overall} | "
                f"Warnings: {len(warnings)}"
            ),
            confidence=grounding_score,
            reasoning=reasoning,
            evidence=evidence,
            metadata={
                "grounding_score": grounding_score,
                "overall_assessment": overall,
                "warning_count": len(warnings),
                "warnings": warnings,
                "positive_aspects": result.get("positive_aspects", []),
                "is_rbi_reportable": state.get("is_rbi_reportable", False),
            },
        )

    except Exception as e:
        # Grounding failure — flag for human review conservatively
        grounding_score = 0.5
        warnings = [{
            "type": "SYSTEM_ERROR",
            "claim": "Grounding check failed",
            "issue": str(e),
            "suggestion": "Human agent must manually verify all claims in draft"
        }]
        overall = "VERIFY_BEFORE_SEND"

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision=f"Grounding check failed — VERIFY_BEFORE_SEND (safe default)",
            confidence=grounding_score,
            reasoning=f"Grounding error: {str(e)}. Draft flagged for manual verification.",
            metadata={
                "grounding_score": grounding_score,
                "warning_count": 1,
                "error": str(e),
            },
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    return {
        "grounding_score": grounding_score,
        "grounding_warnings": warnings,
        "current_agent": agent_name,
        "explanation_trace": [output.model_dump()],
        "errors": [str(output.error_message)] if output.error_message else [],
    }
# ── NODE 7: Routing Node (Agent 10) + conditional Agent 10.5 ─────────────────
async def routing_node(state: PipelineState) -> dict:
    """
    Agent 10 — Risk-Aware Routing (deterministic, no LLM).

    Routes:
      AUTO     → execute_auto_response() (confidence >= 95%)
      ESCALATE → Agent 10.5 analyze_escalation(), then optional shadow mode
      HUMAN    → override rules fired, assign tier_hint (default 4)
    """
    agent_name = "Risk-Aware Routing"
    agent_order = 10
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        grounding_warnings = state.get("grounding_warnings", [])
        grounding_score = state.get("grounding_score", 1.0)

        warning_count = len(grounding_warnings)
        if warning_count == 0:
            grounding_assessment = "SAFE_TO_SEND"
        elif warning_count <= 2:
            grounding_assessment = "VERIFY_BEFORE_SEND"
        else:
            grounding_assessment = "DO_NOT_SEND"

        result = make_routing_decision(
            complaint_id=complaint_id,
            category=state.get("category", "General Banking"),
            compliance_category=state.get("compliance_category", "NOT_APPLICABLE"),
            is_rbi_reportable=state.get("is_rbi_reportable", False),
            sentiment=state.get("sentiment", "Neutral"),
            severity=state.get("severity", 3),
            severity_score=state.get("severity_score", 5.0),
            urgency_score=state.get("urgency_score", 5.0),
            escalation_flag=state.get("escalation_flag", False),
            confidence_score=state.get("confidence_score", 0.5),
            grounding_score=grounding_score,
            grounding_assessment=grounding_assessment,
        )

        route = result["route"]
        risk_score = result["risk_score"]
        sla_deadline = result["sla_deadline"]
        reasoning = result["reasoning"]
        override_triggered = result["override_triggered"]

        evidence = []
        if override_triggered:
            evidence = [f"OVERRIDE: {r[:80]}" for r in result["override_rules"][:3]]
        else:
            evidence = result.get("routing_factors", [])[:3]

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.COMPLETE,
            decision=(
                f"{route} | Risk: {risk_score:.3f}"
                + (" | OVERRIDE" if override_triggered else "")
                + (f" | Tier hint: {result['tier_hint']}" if result.get("tier_hint") else "")
            ),
            confidence=1.0 - risk_score,
            reasoning=reasoning,
            evidence=evidence,
            metadata={
                "route": route,
                "risk_score": risk_score,
                "risk_breakdown": result.get("risk_breakdown", {}),
                "sla_deadline": sla_deadline,
                "override_triggered": override_triggered,
                "override_rules": result.get("override_rules", []),
                "tier_hint": result.get("tier_hint"),
                "confidence_gate_applied": result.get("confidence_gate_applied", False),
            },
        )

    except Exception as e:
        route = "HUMAN"
        risk_score = 1.0
        sla_deadline = None
        result = {
            "route": "HUMAN",
            "override_triggered": False,
            "risk_score": 1.0,
            "risk_breakdown": {},
            "tier_hint": 4,
            "override_rules": [],
            "routing_factors": [],
            "confidence_gate_applied": False,
        }
        override_triggered = False

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision="HUMAN (routing failed — safe default)",
            confidence=0.0,
            reasoning=f"Routing engine error: {str(e)}. Defaulting to human review.",
            metadata={"route": "HUMAN", "error": str(e)},
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    # ── Dispatch based on route ──────────────────────────────────────────
    auto_response_result = {}
    assigned_tier = result.get("tier_hint")
    escalation_decision = None
    response_tier = "human_review"
    escalation_trace = []
    formatted_response = None
    notification_channel = None
    customer_notified_at = None
    escalation_info_out = None

    if route == "AUTO" and not override_triggered:
        from app.services.auto_responder import execute_auto_response
        from app.tasks.kb_enrichment import schedule_kb_enrichment

        auto_response_result = execute_auto_response(
            complaint_id   = complaint_id,
            customer_id    = state.get("customer_id", ""),
            channel        = state.get("channel", "web"),
            draft_response = state.get("draft_response", ""),
            tier           = "full_auto",
            confidence_score = state.get("confidence_score", 0.5),
            tier_level     = state.get("current_tier", 1),
            sla_deadline   = state.get("rbi_tat_deadline"),
        )
        response_tier        = "full_auto"
        formatted_response   = auto_response_result.get("formatted_response")
        notification_channel = auto_response_result.get("notification_channel")
        customer_notified_at = auto_response_result.get("customer_notified_at")
        escalation_info_out  = auto_response_result.get("escalation_info")

        # Emit SSE "response_sent" so the frontend can show a real-time preview
        await event_bus.publish(complaint_id, {
            "event":               "response_sent",
            "tier":                state.get("current_tier", 1),
            "confidence":          state.get("confidence_score", 0.5),
            "notification_channel": notification_channel,
            "sent_at":             customer_notified_at,
            "preview":             auto_response_result.get("formatted_response", "")[:150],
        })

        # Schedule background KB enrichment after 24 h
        import asyncio as _asyncio
        _asyncio.create_task(
            schedule_kb_enrichment(
                complaint_id     = complaint_id,
                draft_response   = state.get("draft_response", ""),
                confidence_score = state.get("confidence_score", 0.5),
                tier_level       = state.get("current_tier", 1),
            )
        )

    elif route == "ESCALATE":
        from app.services.agents.esclation_analyzer import analyze_escalation, execute_shadow_mode

        esc_start = await _agent_start(complaint_id, "Escalation Analyzer", 11)

        escalation_result = analyze_escalation(
            complaint_id=complaint_id,
            complaint_text=state.get("masked_text", ""),
            category=state.get("category", "General Banking"),
            compliance_category=state.get("compliance_category", "NOT_APPLICABLE"),
            is_rbi_reportable=state.get("is_rbi_reportable", False),
            sentiment=state.get("sentiment", "Neutral"),
            severity=state.get("severity", 3),
            confidence_score=state.get("confidence_score", 0.5),
            grounding_score=state.get("grounding_score", 1.0),
            authority_sufficient=state.get("authority_sufficient", True),
            draft_response=state.get("draft_response", ""),
            current_tier=state.get("current_tier", 1),
            risk_score=result["risk_score"],
            risk_breakdown=result["risk_breakdown"],
        )

        assigned_tier = escalation_result["target_tier"]
        escalation_decision = escalation_result["decision"]
        response_tier = escalation_result.get("target_tier_label", "human_review")

        esc_output = AgentOutput(
            agent_name="Escalation Analyzer",
            agent_order=11,
            status=AgentStatus.COMPLETE,
            decision=(
                f"{escalation_result['decision']} → Tier {assigned_tier} "
                f"({escalation_result['target_tier_label']})"
            ),
            confidence=escalation_result["confidence_score"],
            reasoning=escalation_result["reasoning"],
            evidence=escalation_result.get("signals_detected", [])[:3],
            metadata={
                "decision": escalation_result["decision"],
                "target_tier": assigned_tier,
                "target_tier_label": escalation_result["target_tier_label"],
                "rule_triggered": escalation_result["rule_triggered"],
                "sla_hours": escalation_result["sla_hours"],
                "shadow_eligible": escalation_result["shadow_eligible"],
                "risk_score": escalation_result["risk_score"],
            },
        )
        await _agent_complete(complaint_id, esc_output, esc_start)
        escalation_trace = [esc_output.model_dump()]

        # ── HUMAN_AT_CURRENT_TIER: assign to queue at current tier ──────────
        if escalation_result["decision"] == "HUMAN_AT_CURRENT_TIER":
            from app.services.queue_service import assign_to_queue

            # current_tier may be 0 if complaint came via standard route; enforce >= 1
            _hat_tier = max(state.get("current_tier") or 1, 1)
            queue_result = assign_to_queue(
                complaint_id  = complaint_id,
                tier_level    = _hat_tier,
                urgency_score = state.get("urgency_score", 5.0),
                severity      = state.get("severity", 3),
                severity_score= state.get("severity_score", 5.0),
                category      = state.get("category", "General Banking"),
                sla_deadline  = escalation_result.get("sla_deadline"),
            )

            await event_bus.publish(complaint_id, {
                "event":          "assigned_to_agent",
                "complaint_id":   complaint_id,
                "assigned_to":    queue_result.get("assigned_to"),
                "tier":           _hat_tier,
                "priority":       queue_result.get("priority_score"),
                "queue_position": queue_result.get("queue_position"),
            })

            await event_bus.publish(complaint_id, {
                "event":                "queue_position_updated",
                "complaint_id":         complaint_id,
                "new_position":         queue_result.get("queue_position"),
                "estimated_wait_time":  f"{queue_result.get('estimated_review_time', 12)} min",
            })

            # Store why escalation was not triggered (for agent context)
            from app.db.supabase_client import get_supabase as _get_supabase
            _get_supabase().table("complaints").update({
                "escalation_not_triggered_reason": escalation_result.get("reasoning", ""),
            }).eq("complaint_id", complaint_id).execute()

            response_tier = escalation_result.get("target_tier_label", "human_review")

        # ── ESCALATE → Route 3: Auto-Escalation orchestrator ─────────────
        elif escalation_result["decision"] == "ESCALATE":
            from app.services.escalation_orchestrator import execute_escalation

            esc_orchestrator_result = await execute_escalation(
                complaint_id=complaint_id,
                from_tier=max(state.get("current_tier") or 1, 1),
                to_tier=assigned_tier,
                escalation_reason=escalation_result.get("rule_triggered", "CONFIDENCE_LOW"),
                original_state=dict(state),
                signals_detected=escalation_result.get("signals_detected", []),
                escalation_reasoning=escalation_result.get("reasoning", ""),
            )

            orchestrator_route = esc_orchestrator_result.get("final_route", "human_review")
            final_tier = esc_orchestrator_result.get("final_tier", assigned_tier)
            assigned_tier = final_tier
            response_tier = orchestrator_route

            if orchestrator_route == "auto_respond":
                # Orchestrator already sent the response; surface the outputs
                formatted_response = esc_orchestrator_result.get("formatted_response")
                notification_channel = esc_orchestrator_result.get("notification_channel")
                customer_notified_at = esc_orchestrator_result.get("customer_notified_at")
            else:
                # human_review at the final escalated tier
                from app.services.queue_service import assign_to_queue
                queue_result = assign_to_queue(
                    complaint_id=complaint_id,
                    tier_level=final_tier,
                    urgency_score=state.get("urgency_score", 5.0),
                    severity=state.get("severity", 3),
                    severity_score=state.get("severity_score", 5.0),
                    category=state.get("category", "General Banking"),
                    sla_deadline=escalation_result.get("sla_deadline"),
                )
                await event_bus.publish(complaint_id, {
                    "event": "assigned_to_agent",
                    "complaint_id": complaint_id,
                    "assigned_to": queue_result.get("assigned_to"),
                    "tier": final_tier,
                    "queue_position": queue_result.get("queue_position"),
                    "escalation_path": esc_orchestrator_result.get("escalation_path", []),
                    "stop_reason": esc_orchestrator_result.get("stop_reason"),
                })

            # Carry escalation orchestrator result into state for persistence
            escalation_info_out = {
                "escalation_path": esc_orchestrator_result.get("escalation_path", []),
                "total_escalations": esc_orchestrator_result.get("total_escalations", 0),
                "stop_reason": esc_orchestrator_result.get("stop_reason"),
                "final_tier": final_tier,
            }

    elif route == "HUMAN":
        # Override triggered — direct to tier_hint (fraud → 4, others → 4 default)
        assigned_tier = result.get("tier_hint") or 4
        response_tier = "human_review"

        # ── Insert into agent_queue so the complaint appears in Agent Desk ──
        # This was the missing step — without it tier_pending_at stays null
        # and the queue API never sees the complaint.
        try:
            from app.services.queue_service import assign_to_queue
            queue_result = assign_to_queue(
                complaint_id=complaint_id,
                tier_level=assigned_tier,
                urgency_score=state.get("urgency_score", 5.0),
                severity=state.get("severity", 3),
                severity_score=state.get("severity_score", 5.0),
                category=state.get("category", "General Banking"),
                sla_deadline=state.get("rbi_tat_deadline"),
            )
            await event_bus.publish(complaint_id, {
                "event":          "assigned_to_agent",
                "complaint_id":   complaint_id,
                "assigned_to":    queue_result.get("assigned_to"),
                "tier":           assigned_tier,
                "queue_position": queue_result.get("queue_position"),
                "route":          "HUMAN",
                "override":       True,
            })
        except Exception as _qe:
            # Queue insertion failure must not crash the pipeline
            logger.warning("[ROUTING] HUMAN queue insert failed: %s", _qe)

    # Determine the final tier for the complaint so _save_pipeline_outputs
    # writes the correct current_tier to the DB (never 0).
    _final_tier = max(assigned_tier or state.get("current_tier") or 1, 1)

    return {
        "route":                      route,
        "risk_score":                 risk_score,
        "sla_hours":                  None,
        "rbi_tat_deadline":           sla_deadline,
        "routing_reason":             route,
        "pipeline_status":            "complete",
        "current_agent":              agent_name,
        "explanation_trace":          [output.model_dump()] + escalation_trace,
        "errors":                     [str(output.error_message)] if output.error_message else [],
        "response_tier":              response_tier,
        "tier_number":                _final_tier,
        "auto_response_result":       auto_response_result,
        "assigned_tier":              _final_tier,
        "current_tier":               _final_tier,
        "escalation_decision":        escalation_decision,
        # Auto-response tracking fields (populated when route == "AUTO" or orchestrator auto-responds)
        "formatted_response":         formatted_response,
        "notification_channel":       notification_channel,
        "customer_notified_at":       customer_notified_at,
        "escalation_info":            escalation_info_out,
        # Route 3 escalation tracking
        "escalation_orchestrator_result": locals().get("esc_orchestrator_result"),
    }
# ── GRAPH ASSEMBLY ────────────────────────────────────────────────────────────

def build_pipeline_graph():
    """
    Assemble and compile the LangGraph StateGraph.

    Graph wiring (matches your architecture diagram exactly):
    START → pii → duplicate → [conditional] → fanout → rag →
            resolution → grounding → routing → END

    This function is called ONCE at app startup.
    The compiled graph is reused for every complaint.
    """
    graph = StateGraph(PipelineState)

    # Register all nodes
    graph.add_node("pii_node", pii_node)
    graph.add_node("duplicate_node", duplicate_node)
    graph.add_node("parallel_fanout_node", parallel_fanout_node)
    graph.add_node("rag_node", rag_node)
    graph.add_node("resolution_node", resolution_node)
    graph.add_node("grounding_node", grounding_node)
    graph.add_node("routing_node", routing_node)

    # Entry point
    graph.set_entry_point("pii_node")

    # Sequential edges
    graph.add_edge("pii_node", "duplicate_node")

    # Conditional edge: if duplicate → END, else → fan-out
    graph.add_conditional_edges(
        "duplicate_node",
        route_after_duplicate,
        {
            "parallel_fanout_node": "parallel_fanout_node",
            END: END,
        }
    )

    # Rest of pipeline
    graph.add_edge("parallel_fanout_node", "rag_node")
    graph.add_edge("rag_node", "resolution_node")
    graph.add_edge("resolution_node", "grounding_node")
    graph.add_edge("grounding_node", "routing_node")
    graph.add_edge("routing_node", END)

    return graph.compile()


# Compiled graph — module level singleton, built once at import
pipeline_graph = build_pipeline_graph()