"""
Partial Pipeline Runner

Re-runs only agents 7 → 8 → 9 → 10 → 10.5 after a tier escalation.
Agents 1-6 are skipped: PII masking, duplicate detection, and classification
outputs do not change when the tier changes — reusing them saves 5 LLM calls.

Cost per escalation hop: 4-5 LLM calls (vs 10 for the full pipeline).
"""

import asyncio
from app.services.agents.rag_agent import retrieve_context
from app.services.agents.resolution_agent import generate_tier_aware_resolution
from app.services.agents.grounding_agent import run_grounding_check
from app.services.agents.routing_agent import make_routing_decision
from app.services.agents.esclation_analyzer import analyze_escalation
from app.services.tier_context_manager import get_tier_context
from app.utils.escalation_cost_optimizer import determine_agents_to_rerun


def _normalize_grounding_state(
    score: float | None,
    warnings: list,
) -> tuple[float | None, list]:
    warnings = warnings or []

    if score is None:
        return None, []

    if score == 1.0:
        return 1.0, []

    if score == 0.0:
        has_system_error = any(
            isinstance(w, dict) and w.get("type") == "SYSTEM_ERROR"
            for w in warnings
        )
        if not has_system_error:
            warnings = [{
                "type": "SYSTEM_ERROR",
                "claim": "Grounding state repaired",
                "issue": "Grounding failed but no SYSTEM_ERROR warning was present.",
                "suggestion": "Review the draft manually.",
            }]
        return 0.0, warnings

    return score, warnings


async def run_tier_transition_pipeline(
    complaint_id: str,
    new_tier_level: int,
    original_state: dict,
    from_tier: int,
    excluded_kb_ids: list = None,
) -> dict:
    """
    Re-run agents 7-10.5 at new_tier_level.

    Args:
        complaint_id:     Complaint being escalated.
        new_tier_level:   Target tier for this re-run.
        original_state:   Full pipeline state from the initial run (has category,
                          masked_text, sentiment, etc. — these don't change).
        from_tier:        Previous tier (used to build previous-attempt context).
        excluded_kb_ids:  KB IDs already used at earlier tiers (avoid repetition).

    Returns dict with route, confidence, draft, escalation_decision, etc.
    """
    errors: list[str] = []

    # ── Build tier context ────────────────────────────────────────────────────
    tier_ctx = get_tier_context(complaint_id, new_tier_level, from_tier=from_tier)
    previous_tier_attempts = tier_ctx["previous_attempts_prompt"] or None
    tier_contact_info = tier_ctx["tier_contact_info"]
    tier_name = tier_ctx["tier_name"]

    # ── Agent 7: RAG at new tier ──────────────────────────────────────────────
    context_documents: list = []
    rag_coverage: float = 0.0

    try:
        rag_result = await asyncio.to_thread(
            retrieve_context,
            original_state.get("masked_text", ""),
            original_state.get("category", "General Banking"),
            3,               # n
        )
        context_documents = rag_result.get("documents", [])
        rag_coverage = rag_result.get("tier_kb_coverage_score", 0.0)
    except Exception as e:
        errors.append(f"Agent 7 (RAG) failed at Tier {new_tier_level}: {e}")

    # ── Agent 8: Resolution at new tier with escalation context ──────────────
    draft_response: str = original_state.get("draft_response", "")
    confidence_score: float = 0.5
    authority_sufficient: bool = False
    resolution_result: dict = {}

    try:
        resolution_result = await asyncio.to_thread(
            generate_tier_aware_resolution,
            original_state.get("complaint_text", original_state.get("masked_text", "")),
            original_state.get("masked_text", ""),
            original_state.get("category", "General Banking"),
            original_state.get("sentiment", "Neutral"),
            original_state.get("severity", 3),
            original_state.get("urgency_score", 5.0),
            original_state.get("compliance_category", "NOT_APPLICABLE"),
            original_state.get("is_rbi_reportable", False),
            original_state.get("language", "en"),
            context_documents,
            tier_name,
            tier_contact_info,
            previous_tier_attempts,
        )
        draft_response = resolution_result.get("draft_response", draft_response)
        confidence_score = float(resolution_result.get("confidence", 0.5))
        authority_sufficient = bool(resolution_result.get("authority_sufficient", False))
    except Exception as e:
        errors.append(f"Agent 8 (Resolution) failed at Tier {new_tier_level}: {e}")

    # ── Agent 9: Grounding (conditional on draft delta) ───────────────────────
    previous_draft = original_state.get("draft_response", "")
    grounding_score, grounding_warnings = _normalize_grounding_state(
        original_state.get("grounding_score"),
        original_state.get("grounding_warnings"),
    )

    agents_to_run = determine_agents_to_rerun(
        from_tier, new_tier_level, previous_draft, draft_response
    )

    if 9 in agents_to_run:
        try:
            grounding_result = await asyncio.to_thread(
                run_grounding_check,
                draft_response,
                original_state.get("complaint_text", original_state.get("masked_text", "")),
                original_state.get("is_rbi_reportable", False),
                original_state.get("compliance_category", "NOT_APPLICABLE"),
            )
            grounding_score = grounding_result.get("grounding_score", grounding_score)
            grounding_warnings = grounding_result.get("warnings", grounding_warnings)
        except Exception as e:
            errors.append(f"Agent 9 (Grounding) failed at Tier {new_tier_level}: {e}")
            grounding_score = 0.0
            grounding_warnings = [{
                "type": "SYSTEM_ERROR",
                "claim": "Grounding check failed during escalation re-run",
                "issue": str(e),
                "suggestion": "Human agent must manually verify all claims in draft",
            }]

    # ── Agent 10: Routing decision ────────────────────────────────────────────
    route: str = "ESCALATE"
    risk_score: float = 0.5
    routing_result: dict = {}

    warning_count = len(grounding_warnings)
    if warning_count == 0:
        grounding_assessment = "SAFE_TO_SEND"
    elif warning_count <= 2:
        grounding_assessment = "VERIFY_BEFORE_SEND"
    else:
        grounding_assessment = "DO_NOT_SEND"

    try:
        routing_result = make_routing_decision(
            complaint_id=complaint_id,
            category=original_state.get("category", "General Banking"),
            compliance_category=original_state.get("compliance_category", "NOT_APPLICABLE"),
            is_rbi_reportable=original_state.get("is_rbi_reportable", False),
            sentiment=original_state.get("sentiment", "Neutral"),
            severity=original_state.get("severity", 3),
            severity_score=original_state.get("severity_score", 5.0),
            urgency_score=original_state.get("urgency_score", 5.0),
            escalation_flag=original_state.get("escalation_flag", False),
            confidence_score=confidence_score,
            grounding_score=grounding_score,
            grounding_assessment=grounding_assessment,
        )
        route = routing_result.get("route", "ESCALATE")
        risk_score = routing_result.get("risk_score", 0.5)
    except Exception as e:
        errors.append(f"Agent 10 (Router) failed at Tier {new_tier_level}: {e}")

    # ── Agent 10.5: Escalation Analyzer (only when route == ESCALATE) ─────────
    escalation_decision: str = None
    next_target_tier: int = None
    escalation_result: dict = {}

    if route == "ESCALATE":
        try:
            escalation_result = analyze_escalation(
                complaint_id=complaint_id,
                complaint_text=original_state.get("masked_text", ""),
                category=original_state.get("category", "General Banking"),
                compliance_category=original_state.get("compliance_category", "NOT_APPLICABLE"),
                is_rbi_reportable=original_state.get("is_rbi_reportable", False),
                sentiment=original_state.get("sentiment", "Neutral"),
                severity=original_state.get("severity", 3),
                confidence_score=confidence_score,
                grounding_score=grounding_score,
                authority_sufficient=authority_sufficient,
                draft_response=draft_response,
                current_tier=new_tier_level,
                risk_score=risk_score,
                risk_breakdown=routing_result.get("risk_breakdown", {}),
            )
            escalation_decision = escalation_result.get("decision")
            next_target_tier = escalation_result.get("target_tier")
        except Exception as e:
            errors.append(f"Agent 10.5 (Escalation) failed at Tier {new_tier_level}: {e}")
            escalation_decision = "HUMAN_AT_CURRENT_TIER"

    return {
        "route": route,
        "confidence_score": confidence_score,
        "draft_response": draft_response,
        "root_cause": resolution_result.get("root_cause"),
        "action_steps": resolution_result.get("action_steps", []),
        "authority_sufficient": authority_sufficient,
        "grounding_score": grounding_score,
        "grounding_warnings": grounding_warnings,
        "context_documents": context_documents,
        "rag_coverage": rag_coverage,
        "escalation_decision": escalation_decision,
        "next_target_tier": next_target_tier,
        "escalation_signals": escalation_result.get("signals_detected", []),
        "escalation_reasoning": escalation_result.get("reasoning", ""),
        "risk_score": risk_score,
        "tier_level": new_tier_level,
        "errors": errors,
    }
