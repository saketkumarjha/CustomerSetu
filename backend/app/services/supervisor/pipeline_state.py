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

    # ── Grounding Agent outputs (Phase 8) ────────────────────────────────
    grounding_score: Optional[float]
    grounding_warnings: Optional[list]

    # ── Routing outputs (Phase 9) ────────────────────────────────────────
    route: Optional[str]          # "auto_respond" | "human_review"
    risk_score: Optional[float]
    sla_hours: Optional[int]
    rbi_tat_deadline: Optional[str]
    routing_reason: Optional[str]

    # ── Accumulating lists — operator.add means append, not overwrite ────
    # Each agent appends one AgentOutput dict to this list
    explanation_trace: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]

    # ── Pipeline control ─────────────────────────────────────────────────
    pipeline_status: str   # "started" | "processing" | "complete" | "failed"
    current_agent: Optional[str]