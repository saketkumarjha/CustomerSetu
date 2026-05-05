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
import time
from typing import Literal
from langgraph.graph import StateGraph, END

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
from app.services.agents.resolution_agent import generate_resolution
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
    PHASE 7 — Real GPT-4o resolution generation with dynamic few-shot prompting.
    """
    agent_name = "Resolution Generator"
    agent_order = 8
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        result = await asyncio.to_thread(
            generate_resolution,
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
        )

        draft = result["draft_response"]
        root_cause = result["root_cause"]
        action_steps = result["action_steps"]
        confidence = result["confidence"]
        meets_threshold = result["meets_threshold"]
        never_auto = result["never_auto_respond"]
        category_threshold = result["category_threshold"]
        context_used = result["context_used"]

        reasoning = (
            f"Resolution generated using GPT-4o.\n"
            f"RAG context documents used: {context_used}\n"
            f"Confidence: {confidence:.1%}\n"
            f"Category threshold: {category_threshold:.0%}\n"
            f"Meets auto-respond threshold: {'YES' if meets_threshold else 'NO'}\n"
            + (f"⚠️ NEVER AUTO-RESPOND category — forced to human review\n"
               if never_auto else "")
            + f"Confidence reasoning: {result.get('confidence_reasoning', '')}\n"
            f"Root cause: {root_cause}"
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
# ── NODE 7: Routing Node (Supervisor Final Decision) ─────────────────────────
async def routing_node(state: PipelineState) -> dict:
    """
    PHASE 9 — Real risk-aware routing with RBI override rules.
    Deterministic decision engine — no LLM calls.
    """
    agent_name = "Risk-Aware Routing"
    agent_order = 10
    complaint_id = state["complaint_id"]

    start = await _agent_start(complaint_id, agent_name, agent_order)

    try:
        # Extract grounding assessment from warnings metadata
        grounding_warnings = state.get("grounding_warnings", [])
        grounding_score = state.get("grounding_score", 1.0)

        # Determine overall grounding assessment from warnings count
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
        sla_hours = result["sla_hours"]
        tat_deadline = result["rbi_tat_deadline"]
        reasoning = result["reasoning"]
        override_triggered = result["override_triggered"]

        # Build evidence list — what factors drove the decision
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
                f"{route.upper()} | "
                f"Risk: {risk_score:.3f} | "
                f"SLA: {sla_hours}h"
                + (" | 🚨 OVERRIDE" if override_triggered else "")
                + (f" | 💰 Penalty: ₹{result['penalty_per_day']}/day"
                   if result.get("penalty_per_day") else "")
            ),
            confidence=1.0 - risk_score,
            reasoning=reasoning,
            evidence=evidence,
            metadata={
                "route": route,
                "routing_reason": result["routing_reason"],
                "risk_score": risk_score,
                "risk_breakdown": result.get("risk_breakdown", {}),
                "sla_hours": sla_hours,
                "rbi_tat_deadline": tat_deadline,
                "penalty_per_day": result.get("penalty_per_day", 0),
                "override_triggered": override_triggered,
                "override_rules": result.get("override_rules", []),
                "confidence_check_skipped": result.get("confidence_check_skipped", False),
                "confidence_passed": result.get("confidence_passed"),
                "risk_passed": result.get("risk_passed"),
            },
        )

    except Exception as e:
        route = "human_review"
        risk_score = 1.0
        sla_hours = 24
        tat_deadline = None
        result = {
            "tier": "human_review",
            "tier_number": 3,
            "routing_reason": "error",
            "override_triggered": False,
        }

        output = AgentOutput(
            agent_name=agent_name,
            agent_order=agent_order,
            status=AgentStatus.FAILED,
            decision="HUMAN_REVIEW (routing failed — safe default)",
            confidence=0.0,
            reasoning=f"Routing engine error: {str(e)}. Defaulting to human review.",
            metadata={"route": "human_review", "error": str(e)},
            error_message=str(e),
        )

    await _agent_complete(complaint_id, output, start)

    # ── Auto-response ────────────────────────────────────────────────────
    auto_response_result = {}
    tier = result.get("tier", "human_review")

    if tier in ("full_auto", "shadow") and not result.get("override_triggered"):
        from app.services.auto_responder import execute_auto_response
        auto_response_result = execute_auto_response(
            complaint_id=complaint_id,
            customer_id=state.get("customer_id", ""),
            channel=state.get("channel", "web"),
            draft_response=state.get("draft_response", ""),
            tier=tier,
            confidence_score=state.get("confidence_score", 0.5),
        )

    return {
        "route": route,
        "risk_score": risk_score,
        "sla_hours": sla_hours,
        "rbi_tat_deadline": tat_deadline,
        "routing_reason": result.get("routing_reason", "error"),
        "pipeline_status": "complete",
        "current_agent": agent_name,
        "explanation_trace": [output.model_dump()],
        "errors": [str(output.error_message)] if output.error_message else [],
        "response_tier": result.get("tier", "human_review"),
        "tier_number": result.get("tier_number", 3),
        "auto_response_result": auto_response_result,
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