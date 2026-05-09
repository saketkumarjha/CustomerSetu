from typing import TypedDict, Optional, Annotated
import operator


class PipelineState(TypedDict):
    """
    Shared state object that flows through every LangGraph node.

    Every agent reads from this and writes back a partial update.
    LangGraph merges partial updates back into the state automatically.

    Fields annotated with operator.add ACCUMULATE (lists grow).
    All other fields OVERWRITE (latest value wins).

    This is the single source of truth for one complaint's pipeline run.
    """

    # ── Input ────────────────────────────────────────────────────────────
    complaint_id: str
    customer_id: str
    channel: str
    complaint_text: str
    merged_text: str           # complaint text + image text (from image handler)
    image_url: Optional[str]
    idempotency_key: Optional[str]

    # ── PII Agent outputs (Phase 3) ──────────────────────────────────────
    masked_text: Optional[str]
    language: Optional[str]
    pii_entities_found: Optional[list]

    # ── Duplicate Detection Agent outputs (Phase 4) ──────────────────────
    is_duplicate: Optional[bool]
    duplicate_of: Optional[str]
    duplicate_similarity: Optional[float]

    # ── Parallel Fan-out outputs (Phase 5) ──────────────────────────────
    category: Optional[str]
    category_confidence: Optional[float]

    sentiment: Optional[str]
    urgency_score: Optional[float]
    escalation_flag: Optional[bool]

    compliance_category: Optional[str]
    is_rbi_reportable: Optional[bool]
    rbi_supervisor_override: Optional[str]

    severity: Optional[int]
    severity_score: Optional[float]
    severity_breakdown: Optional[dict]

    # ── RAG Agent outputs (Phase 6) ──────────────────────────────────────
    context_documents: Optional[list]

    # ── Resolution Agent outputs (Phase 7) ──────────────────────────────
    draft_response: Optional[str]
    root_cause: Optional[str]
    action_steps: Optional[list]
    confidence_score: Optional[float]
    authority_sufficient: Optional[bool]

    # ── Grounding Agent outputs (Phase 8) ────────────────────────────────
    grounding_score: Optional[float]
    grounding_warnings: Optional[list]

    # ── Routing outputs (Phase 9 + Agent 10.5) ──────────────────────────
    route: Optional[str]          # "AUTO" | "HUMAN" | "ESCALATE"
    risk_score: Optional[float]
    sla_hours: Optional[int]
    rbi_tat_deadline: Optional[str]
    routing_reason: Optional[str]
    current_tier: Optional[int]        # tier where complaint currently sits (from DB)
    assigned_tier: Optional[int]       # final tier decided by Agent 10 / 10.5
    escalation_decision: Optional[str] # "ESCALATE" | "HUMAN_AT_CURRENT_TIER" (Agent 10.5)

    # ── Auto-response outputs (Route 1: confidence >= 95%) ───────────────
    formatted_response: Optional[str]    # final formatted message sent to customer
    notification_channel: Optional[str]  # channel used for the auto-send
    customer_notified_at: Optional[str]  # ISO datetime of send
    escalation_info: Optional[dict]      # escalation timeline injected into the response

    # ── Auto-Escalation tracking (Route 3) ──────────────────────────────
    escalation_count: Optional[int]
    escalation_path: Optional[list]
    is_escalating: Optional[bool]
    escalation_orchestrator_result: Optional[dict]  # full result from execute_escalation()

    # ── Tier-aware fields (used by resolution_node + _save_pipeline_outputs) ──
    tier_level: Optional[int]
    tier_scope: Optional[str]
    tier_contact_info: Optional[str]
    previous_tier_attempts: Optional[str]
    tier_kb_coverage_score: Optional[float]
    missing_info_indicators: Optional[list]
    resolution_type: Optional[str]

    # ── Accumulating lists — operator.add means append, not overwrite ────
    # Each agent appends one AgentOutput dict to this list
    explanation_trace: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]

    # ── Pipeline control ─────────────────────────────────────────────────
    pipeline_status: str   # "started" | "processing" | "complete" | "failed"
    current_agent: Optional[str]