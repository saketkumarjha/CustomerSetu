"""
Agent Context Service — Prepare the complete review package for a human agent.

Fetches all upstream agent outputs for a complaint and packages them into a
single JSON-serialisable dict that the agent dashboard API serves.
"""

from app.db.supabase_client import get_supabase


def prepare_review_context(complaint_id: str) -> dict:
    """
    Return full context dict for a human agent reviewing complaint_id.

    Raises ValueError if complaint not found.
    """
    supabase = get_supabase()

    c_result = (
        supabase.table("complaints")
        .select("*")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not c_result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    c = c_result.data[0]

    # ── Agent decision audit trail ───────────────────────────────────────────
    dec_result = (
        supabase.table("agent_decisions")
        .select("*")
        .eq("complaint_id", complaint_id)
        .order("created_at")
        .execute()
    )
    agent_decisions = dec_result.data or []

    # Pull specific agent outputs from the flat complaints record
    confidence = c.get("confidence_score") or 0.0

    # Build confidence breakdown from grounding + category signals
    grounding_score = c.get("grounding_score") or 0.0
    category_conf   = c.get("category_confidence") or 0.0
    confidence_breakdown = {
        "overall_confidence": confidence,
        "grounding_score":    grounding_score,
        "category_confidence": category_conf,
    }

    # ── Escalation reasoning (from audit trail — Agent 10.5 row) ────────────
    escalation_reasoning = c.get("escalation_not_triggered_reason") or ""
    esc_agent = next(
        (d for d in agent_decisions if d.get("agent_name") == "Escalation Analyzer"),
        None,
    )
    if esc_agent:
        escalation_reasoning = esc_agent.get("reasoning") or escalation_reasoning

    # ── Suggested actions ────────────────────────────────────────────────────
    suggested_actions = [
        "Accept draft and send to customer",
        "Edit response to add missing details, then send",
        "Reject AI draft — write a manual response",
    ]
    if c.get("current_tier", 1) < 4:
        suggested_actions.append(
            f"Manually escalate to Tier {(c.get('current_tier') or 1) + 1} "
            f"if this tier lacks authority"
        )

    # ── Similar past cases (from kb retrieval) ───────────────────────────────
    context_docs = c.get("context_documents") or []

    # ── Customer history (placeholder — extend when CBS integration available) ─
    customer_history: dict = {
        "note": "CBS integration pending — no prior history available",
        "customer_id": c.get("customer_id"),
    }

    # ── Timeline ─────────────────────────────────────────────────────────────
    timeline = [
        {"event": "submitted",      "timestamp": c.get("created_at")},
        {"event": "pipeline_start", "timestamp": c.get("review_started_at") or c.get("created_at")},
        {"event": "queue_assigned", "timestamp": c.get("updated_at")},
    ]

    return {
        "complaint_id": complaint_id,
        "complaint_summary": {
            "masked_text":  c.get("masked_text") or c.get("complaint_text", ""),
            "channel":      c.get("channel"),
            "customer_id":  c.get("customer_id"),
            "submitted_at": c.get("created_at"),
            "current_tier": c.get("current_tier"),
            "status":       c.get("status"),
        },
        "ai_analysis": {
            "classification": {
                "category":    c.get("category"),
                "confidence":  c.get("category_confidence"),
            },
            "sentiment": {
                "emotion":       c.get("sentiment"),
                "urgency_score": c.get("urgency_score"),
                "escalation_flag": c.get("escalation_flag"),
            },
            "severity": {
                "level":          c.get("severity"),
                "score":          c.get("severity_score"),
                "breakdown":      c.get("severity_breakdown"),
            },
            "rbi_compliance": {
                "compliance_category": c.get("compliance_category"),
                "is_rbi_reportable":   c.get("is_rbi_reportable"),
                "tat_deadline":        c.get("rbi_tat_deadline"),
            },
        },
        "draft_response": {
            "text":                c.get("draft_response"),
            "confidence":          confidence,
            "confidence_breakdown": confidence_breakdown,
            "root_cause":          c.get("root_cause"),
            "action_steps":        c.get("action_steps") or [],
            "grounding_warnings":  c.get("grounding_warnings") or [],
            "can_be_accepted":     confidence >= 0.80,
        },
        "escalation_analysis": {
            "should_escalate":  False,
            "reasoning":        escalation_reasoning,
            "signals_detected": [],
        },
        "suggested_actions": suggested_actions,
        "knowledge_references": [
            {
                "category":        doc.get("category"),
                "similarity":      doc.get("similarity"),
                "resolution_text": doc.get("resolution_text"),
            }
            for doc in context_docs[:3]
        ],
        "similar_cases": [],
        "customer_history": customer_history,
        "timeline": timeline,
        "agent_decisions_trace": [
            {
                "agent": d.get("agent_name"),
                "decision": d.get("decision"),
                "confidence": d.get("confidence"),
            }
            for d in agent_decisions
        ],
    }
