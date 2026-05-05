"""
Agent Feedback Service

Handles the internal quality signal loop:
  Agent reviews AI draft → accept/edit/reject/escalate
  → stores score
  → auto-promotes to knowledge_base if accepted
  → accumulates fine_tune_dataset
  → invalidates RAG cache for similar complaints

Agent score mapping:
  accept   → 1.0  (AI draft was perfect)
  edit     → 0.5  (AI draft was useful but needed improvement)
  reject   → 0.0  (AI draft was not useful)
  escalate → -0.5 (wrong routing — needed specialist)
"""

from app.db.supabase_client import get_supabase
from app.services.agents.rag_agent import retrieve_context

AGENT_SCORE_MAP = {
    "accept": 1.0,
    "edit": 0.5,
    "reject": 0.0,
    "escalate": -0.5,
}

VALID_ACTIONS = set(AGENT_SCORE_MAP.keys())


def process_agent_feedback(
    complaint_id: str,
    agent_id: str,
    action: str,
    original_draft: str,
    final_response: str | None,
    rejection_reason: str | None,
) -> dict:
    """
    Process agent feedback on an AI-generated draft.

    Steps:
    1. Validate action
    2. Calculate agent_score
    3. Store in agent_feedback table
    4. Auto-promote to knowledge_base if accepted
    5. Accumulate fine_tune_dataset row
    6. Return result with promotion status
    """
    supabase = get_supabase()

    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Invalid action '{action}'. "
            f"Must be one of: {', '.join(VALID_ACTIONS)}"
        )

    agent_score = AGENT_SCORE_MAP[action]

    # Fetch complaint for category and masked_text
    complaint_result = (
        supabase.table("complaints")
        .select("category, masked_text, compliance_category, is_rbi_reportable")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not complaint_result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    complaint = complaint_result.data[0]
    category = complaint.get("category", "General Banking")
    masked_text = complaint.get("masked_text", "")

    # Store agent feedback record
    feedback_record = {
        "complaint_id": complaint_id,
        "agent_id": agent_id,
        "action": action,
        "original_draft": original_draft,
        "final_response": final_response,
        "agent_score": agent_score,
    }

    supabase.table("agent_feedback").insert(feedback_record).execute()

    # Auto-promote to knowledge base if accepted
    promoted_to_kb = False
    if action == "accept" and final_response:
        _promote_to_knowledge_base(
            resolution_text=final_response,
            category=category,
            quality_score=1.0,
        )
        promoted_to_kb = True

    # Accumulate fine_tune_dataset
    _accumulate_fine_tune_record(
        complaint_id=complaint_id,
        complaint_text=masked_text,
        ai_draft=original_draft,
        agent_corrected_response=final_response,
        agent_rating=agent_score,
        category=category,
    )

    return {
        "complaint_id": complaint_id,
        "agent_id": agent_id,
        "action": action,
        "agent_score": agent_score,
        "promoted_to_knowledge_base": promoted_to_kb,
        "fine_tune_record_added": True,
    }


def _promote_to_knowledge_base(
    resolution_text: str,
    category: str,
    quality_score: float,
) -> None:
    """
    Add an accepted resolution to the knowledge base.
    This is the core RAG improvement mechanism —
    every accepted resolution improves future responses.
    """
    from openai import OpenAI
    from app.core.config import get_settings

    supabase = get_supabase()
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # Generate embedding for the resolution text
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=resolution_text,
        dimensions=settings.openai_embedding_dimension,
    )
    embedding = response.data[0].embedding

    supabase.table("knowledge_base").insert({
        "resolution_text": resolution_text,
        "category": category,
        "source": "agent",
        "quality_score": quality_score,
        "embedding": embedding,
    }).execute()


def _accumulate_fine_tune_record(
    complaint_id: str,
    complaint_text: str,
    ai_draft: str,
    agent_corrected_response: str | None,
    agent_rating: float,
    category: str,
) -> None:
    """
    Store one training data point in fine_tune_dataset.

    Format follows OpenAI fine-tuning JSONL standard:
    prompt   = masked complaint text
    completion = what the agent actually sent (corrected or accepted draft)

    When you have 500+ records, export via Phase 16 endpoint
    and fine-tune LLaMA on Together AI / Hugging Face.
    """
    supabase = get_supabase()

    supabase.table("fine_tune_dataset").insert({
        "complaint_id": complaint_id,
        "complaint_text": complaint_text,
        "ai_draft": ai_draft,
        "agent_corrected_response": agent_corrected_response or ai_draft,
        "agent_rating": agent_rating,
        "category": category,
        "exported": False,
    }).execute()