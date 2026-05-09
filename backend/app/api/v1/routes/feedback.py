"""
Feedback Routes — Agent and Customer feedback endpoints

Agent feedback:   POST /api/v1/feedback/agent
Customer CSAT:    POST /api/v1/feedback/customer
Dataset export:   GET  /api/v1/feedback/export-dataset
CSAT trigger:     POST /api/v1/feedback/trigger-survey/{complaint_id}
"""

import json
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from app.models.feedback import AgentFeedbackInput, CustomerFeedbackInput
from app.services.feedback.agent_feedback import process_agent_feedback
from app.services.feedback.customer_feedback import process_customer_feedback
from app.db.supabase_client import get_supabase

router = APIRouter()


@router.post(
    "/agent",
    status_code=status.HTTP_201_CREATED,
    summary="Submit agent feedback on AI draft",
)
async def submit_agent_feedback(
    feedback: AgentFeedbackInput,
    background_tasks: BackgroundTasks,
):
    """
    Submit agent feedback on AI-generated draft response.

    Two background processes fire immediately after response is returned:
    1. KB promotion  — if accepted, resolution added to knowledge_base
    2. Dataset save  — training data point stored in fine_tune_dataset

    Agent sees instant response. Background work happens asynchronously.
    """


    if feedback.action in ("accept", "edit") and not feedback.final_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"final_response is required for action '{feedback.action}'"
        )

    if feedback.action == "reject" and not feedback.rejection_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rejection_reason is required for action 'reject'"
        )

    try:
        # Synchronous: just store the feedback record + calculate score
        # Fast — single Supabase insert
        result = _store_agent_feedback_record(
            complaint_id=feedback.complaint_id,
            agent_id=feedback.agent_id,
            action=feedback.action,
            original_draft=feedback.original_draft,
            final_response=feedback.final_response,
            rejection_reason=feedback.rejection_reason,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ── Async Process 1: KB Promotion ─────────────────────────────────────
    # Fires AFTER response is returned — does not block the agent
    if feedback.action == "accept" and feedback.final_response:
        background_tasks.add_task(
            _async_kb_promotion,
            complaint_id=feedback.complaint_id,
            final_response=feedback.final_response,
            category=result["category"],
        )

    # ── Async Process 2: Fine-tune Dataset Accumulation ───────────────────
    # Fires AFTER response is returned — does not block the agent
    background_tasks.add_task(
        _async_dataset_save,
        complaint_id=feedback.complaint_id,
        complaint_text=result["masked_text"],
        ai_draft=feedback.original_draft,
        agent_corrected_response=feedback.final_response,
        agent_rating=result["agent_score"],
        category=result["category"],
    )

    return {
        "status": "recorded",
        "complaint_id": feedback.complaint_id,
        "agent_id": feedback.agent_id,
        "action": feedback.action,
        "agent_score": result["agent_score"],
        "kb_promotion": "queued_async" if feedback.action == "accept" else "not_applicable",
        "fine_tune_record": "queued_async",
        "message": (
            f"Feedback recorded instantly. "
            f"Agent score: {result['agent_score']}. "
            + ("KB promotion running in background. "
               if feedback.action == "accept" else "")
            + "Training data point saving in background."
        ),
    }

@router.post(
    "/trigger-survey/{complaint_id}",
    summary="Trigger CSAT survey for a complaint (simulated)",
)
async def trigger_csat_survey(complaint_id: str):
    """
    Simulate sending a CSAT survey to the customer.

    In production: called by a background scheduler 24-48hrs after resolution.
    For POC: called manually for demo purposes.

    Updates complaint status to 'awaiting_feedback'.
    """
    supabase = get_supabase()

    result = (
        supabase.table("complaints")
        .select("complaint_id, status, pipeline_status, route")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint {complaint_id} not found."
        )

    complaint = result.data[0]

    if complaint.get("pipeline_status") != "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot trigger survey — pipeline has not completed yet."
        )

    # Update status to awaiting_feedback
    supabase.table("complaints").update(
        {"status": "awaiting_feedback"}
    ).eq("complaint_id", complaint_id).execute()

    return {
        "complaint_id": complaint_id,
        "survey_triggered": True,
        "status_updated_to": "awaiting_feedback",
        "message": (
            "CSAT survey triggered. "
            "In production, an email/SMS would be sent to the customer. "
            "For demo: use POST /api/v1/feedback/customer to submit ratings."
        ),
        "survey_fields": {
            "rating": "1-5 stars (required)",
            "issue_tags": "too_slow | wrong_solution | rude | incomplete (optional)",
            "feedback_text": "Free text (optional, Presidio will mask PII)",
        },
    }


@router.get(
    "/export-dataset",
    summary="Export fine-tuning dataset as JSONL",
)
async def export_fine_tune_dataset(
    min_combined_score: float = Query(
        default=0.0,
        description="Minimum combined RL score filter (0.0 = all records)"
    ),
    category: str = Query(
        default=None,
        description="Filter by complaint category"
    ),
    only_agent_accepted: bool = Query(
        default=False,
        description="Only export agent-accepted records (agent_rating=1.0)"
    ),
    preview: bool = Query(
        default=False,
        description="Preview mode — returns JSON stats without downloading"
    ),
):
    """
    Export accumulated agent feedback as JSONL for LLaMA fine-tuning.

    Each line format:
    {
      "prompt": "<masked complaint text>",
      "completion": "<agent final response>",
      "category": "<complaint category>",
      "agent_rating": 0.0-1.0,
      "customer_rating": 1-5 or null,
      "combined_score": 0.0-1.0
    }

    V2 Fine-tuning path:
      1. Export this JSONL (500+ records recommended)
      2. Upload to Together AI / Hugging Face
      3. Fine-tune LLaMA-3 8B on your banking data
      4. Replace Groq endpoint with your custom model
      5. Real RLHF becomes possible
    """
    supabase = get_supabase()

    query = (
        supabase.table("fine_tune_dataset")
        .select("*")
        .eq("exported", False)
    )

    if min_combined_score > 0:
        query = query.gte("combined_score", min_combined_score)

    if category:
        query = query.eq("category", category)

    if only_agent_accepted:
        query = query.eq("agent_rating", 1.0)

    result = query.execute()
    records = result.data or []

    # ── Preview mode ──────────────────────────────────────────────────────
    if preview:
        category_dist = {}
        rating_dist = {"1.0": 0, "0.5": 0, "0.0": 0}
        for r in records:
            cat = r.get("category", "Unknown")
            category_dist[cat] = category_dist.get(cat, 0) + 1
            ar = str(r.get("agent_rating", 0.0))
            if ar in rating_dist:
                rating_dist[ar] += 1

        avg_score = (
            round(
                sum(r.get("combined_score") or 0 for r in records)
                / len(records), 3
            )
            if records else 0
        )

        return {
            "preview_mode": True,
            "total_records_to_export": len(records),
            "avg_combined_score": avg_score,
            "by_category": category_dist,
            "by_agent_rating": {
                "accepted (1.0)": rating_dist["1.0"],
                "edited (0.5)": rating_dist["0.5"],
                "rejected (0.0)": rating_dist["0.0"],
            },
            "fine_tuning_readiness": (
                "✅ Ready (500+ records)"
                if len(records) >= 500
                else f"⚠️ Need more data ({len(records)}/500 records)"
            ),
            "hint": "Remove ?preview=true to download the actual JSONL file",
        }

    if not records:
        return {
            "message": "No new records to export.",
            "total_records": 0,
            "hint": "Submit complaints and provide agent feedback to accumulate data.",
        }

    # ── Mark as exported ──────────────────────────────────────────────────
    ids = [r["id"] for r in records]
    supabase.table("fine_tune_dataset").update(
        {"exported": True}
    ).in_("id", ids).execute()

    # ── Stream as JSONL ───────────────────────────────────────────────────
    def generate_jsonl():
        for record in records:
            line = {
                "prompt": record.get("complaint_text", ""),
                "completion": (
                    record.get("agent_corrected_response")
                    or record.get("ai_draft", "")
                ),
                "category": record.get("category", ""),
                "agent_rating": record.get("agent_rating", 0.0),
                "customer_rating": record.get("customer_rating"),
                "combined_score": record.get("combined_score"),
            }
            yield json.dumps(line, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate_jsonl(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": "attachment; filename=fine_tune_dataset.jsonl",
            "X-Total-Records": str(len(records)),
        },
    )


@router.get(
    "/dataset-stats",
    summary="Fine-tune dataset statistics",
)
async def get_dataset_stats():
    """
    Dataset ki current state — fine-tuning ke liye kitna data ready hai.
    """
    supabase = get_supabase()

    all_result = supabase.table("fine_tune_dataset").select(
        "agent_rating, customer_rating, combined_score, category, exported"
    ).execute()

    records = all_result.data or []

    if not records:
        return {
            "total_records": 0,
            "message": "No training data yet.",
        }

    unexported = [r for r in records if not r.get("exported")]
    exported = [r for r in records if r.get("exported")]

    accepted = [r for r in records if r.get("agent_rating") == 1.0]
    edited = [r for r in records if r.get("agent_rating") == 0.5]
    rejected = [r for r in records if r.get("agent_rating") == 0.0]

    combined_scores = [
        r["combined_score"] for r in records
        if r.get("combined_score") is not None
    ]

    cat_dist = {}
    for r in records:
        cat = r.get("category", "Unknown")
        cat_dist[cat] = cat_dist.get(cat, 0) + 1

    return {
        "total_records": len(records),
        "unexported_records": len(unexported),
        "exported_records": len(exported),
        "quality_breakdown": {
            "accepted_agent_1.0": len(accepted),
            "edited_agent_0.5": len(edited),
            "rejected_agent_0.0": len(rejected),
        },
        "avg_combined_score": round(
            sum(combined_scores) / len(combined_scores), 3
        ) if combined_scores else 0,
        "by_category": cat_dist,
        "fine_tuning_readiness": {
            "current": len(records),
            "recommended_minimum": 500,
            "percentage": round(len(records) / 500 * 100, 1),
            "status": (
                "✅ Ready for fine-tuning"
                if len(records) >= 500
                else f"⚠️ Collecting data ({len(records)}/500)"
            ),
        },
        "next_steps": (
            "Export via GET /api/v1/feedback/export-dataset "
            "and upload to Together AI or Hugging Face"
            if len(records) >= 500
            else f"Need {500 - len(records)} more feedback records"
        ),
    }


@router.get(
    "/dataset-records",
    summary="List accumulated fine_tune_dataset rows",
)
async def list_dataset_records(
    limit: int = Query(50, ge=1, le=200),
):
    """
    Rows are created when agents submit feedback on an AI draft (complaint detail panel)
    or other flows that call `_accumulate_fine_tune_record`. Used by the Feedback UI table.
    """
    supabase = get_supabase()

    try:
        result = (
            supabase.table("fine_tune_dataset")
            .select("*")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load dataset rows: {e!s}",
        ) from e

    rows_out = []
    for r in result.data or []:
        text = str(r.get("complaint_text") or "")
        preview = text if len(text) <= 200 else text[:200] + "…"
        rows_out.append(
            {
                "id": r.get("id"),
                "complaint_id": r.get("complaint_id"),
                "category": r.get("category"),
                "agent_rating": r.get("agent_rating"),
                "customer_rating": r.get("customer_rating"),
                "combined_score": r.get("combined_score"),
                "exported": r.get("exported"),
                "created_at": r.get("created_at"),
                "complaint_preview": preview,
            }
        )

    return {
        "limit": limit,
        "count": len(rows_out),
        "records": rows_out,
        "source_note": (
            "Each row is one training example accumulated after agent feedback "
            "(Approve / edit draft / reject) on the complaint detail screen, "
            "saved asynchronously to fine_tune_dataset."
        ),
    }


@router.post(
    "/customer",
    status_code=status.HTTP_201_CREATED,
    summary="Submit customer CSAT feedback",
)
async def submit_customer_feedback(feedback: CustomerFeedbackInput):
    """
    Submit customer satisfaction feedback after complaint resolution.

    Rating scale:
    1 = Very Dissatisfied
    2 = Dissatisfied
    3 = Neutral
    4 = Satisfied
    5 = Very Satisfied

    Issue tags (optional, multi-select):
    - too_slow
    - wrong_solution
    - rude
    - incomplete

    Free text feedback (optional):
    Presidio automatically masks PII before storing.

    Combined RL Score = (agent_score × 0.4) + (customer_rating × 0.6)
    Score ≥ 0.85 → auto-promoted to knowledge base
    """
    try:
        result = process_customer_feedback(
            complaint_id=feedback.complaint_id,
            customer_id=feedback.customer_id,
            rating=feedback.rating,
            issue_tags=feedback.issue_tags or [],
            feedback_text=feedback.feedback_text,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process customer feedback: {str(e)}"
        )

    return {
        "status": "recorded",
        **result,
        "message": (
            f"CSAT recorded. Rating: {result['rating']}/5. "
            f"Combined RL score: {result['combined_rl_score']:.2f}. "
            + ("✅ High quality — promoted to knowledge base. "
               if result["kb_promoted"] else "")
            + ("📊 Router calibration triggered."
               if result["calibration_triggered"] else "")
        ),
    }



# ── Sync helper — fast, blocks only for DB insert ────────────────────────────

def _store_agent_feedback_record(
    complaint_id: str,
    agent_id: str,
    action: str,
    original_draft: str,
    final_response: str | None,
    rejection_reason: str | None,
) -> dict:
    """
    Store the core feedback record synchronously.
    Returns agent_score, category, masked_text for background tasks.
    """
    from app.services.feedback.agent_feedback import AGENT_SCORE_MAP, VALID_ACTIONS
    supabase = get_supabase()

    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid action '{action}'")

    agent_score = AGENT_SCORE_MAP[action]

    # Fetch complaint metadata
    complaint_result = (
        supabase.table("complaints")
        .select("category, masked_text")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not complaint_result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    complaint = complaint_result.data[0]

    # Store feedback record — fast single insert
    supabase.table("agent_feedback").insert({
        "complaint_id": complaint_id,
        "agent_id": agent_id,
        "action": action,
        "original_draft": original_draft,
        "final_response": final_response,
        "agent_score": agent_score,
    }).execute()

    return {
        "agent_score": agent_score,
        "category": complaint.get("category", "General Banking"),
        "masked_text": complaint.get("masked_text", ""),
    }


# ── Async Process 1: KB Promotion ────────────────────────────────────────────

def _async_kb_promotion(
    complaint_id: str,
    final_response: str,
    category: str,
) -> None:
    """
    Background task: promote accepted resolution to knowledge_base.

    Called after the HTTP response is already returned to the agent.
    Failure here is logged but does NOT affect the feedback record.

    This is the core RAG improvement loop:
    Every accepted resolution → knowledge_base → better future responses.
    """
    try:
        from app.services.feedback.agent_feedback import _promote_to_knowledge_base
        _promote_to_knowledge_base(
            resolution_text=final_response,
            category=category,
            quality_score=1.0,
        )
        print(
            f"[KB_PROMOTION] ✅ {complaint_id} — "
            f"Resolution added to knowledge_base for category: {category}"
        )
    except Exception as e:
        # Non-fatal — log and continue
        # KB promotion failure must never affect the agent's workflow
        print(f"[KB_PROMOTION] ❌ {complaint_id} — Error: {e}")


# ── Async Process 2: Fine-tune Dataset Save ───────────────────────────────────

def _async_dataset_save(
    complaint_id: str,
    complaint_text: str,
    ai_draft: str,
    agent_corrected_response: str | None,
    agent_rating: float,
    category: str,
) -> None:
    """
    Background task: accumulate training data in fine_tune_dataset.

    Called after the HTTP response is already returned to the agent.
    Each row = one (prompt, completion) pair for future LLaMA fine-tuning.

    When you have 500+ rows:
    → GET /api/v1/feedback/export-dataset
    → Upload JSONL to Together AI or Hugging Face
    → Fine-tune LLaMA on your banking complaint style
    → Replace Groq endpoint with your custom model
    """
    try:
        from app.services.feedback.agent_feedback import _accumulate_fine_tune_record
        _accumulate_fine_tune_record(
            complaint_id=complaint_id,
            complaint_text=complaint_text,
            ai_draft=ai_draft,
            agent_corrected_response=agent_corrected_response,
            agent_rating=agent_rating,
            category=category,
        )
        print(
            f"[DATASET] ✅ {complaint_id} — "
            f"Training data point added. Rating: {agent_rating}"
        )
    except Exception as e:
        print(f"[DATASET] ❌ {complaint_id} — Error: {e}")