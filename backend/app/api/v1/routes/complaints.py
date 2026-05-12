"""
Complaint Routes — Unified entry point for all complaint operations

Routes:
  POST /api/v1/complaints/submit          — New complaint submission
  GET  /api/v1/complaints/                — List with filters
  GET  /api/v1/complaints/{id}            — Single complaint detail
  POST /api/v1/complaints/{id}/shadow-override — Shadow mode override
"""
import uuid
from fastapi import (
    APIRouter, File, Form, UploadFile,
    HTTPException, status, Request,
    Header, Query, Body
)
from typing import Optional, Annotated
import re

from app.models.complaint import ComplaintSubmitResponse
from app.services.image_handler import process_image_attachment
from app.middleware.idempotency import check_idempotency, store_idempotency_key
from app.middleware.rate_limiter import limiter
from app.db.supabase_client import get_supabase
from app.core.config import get_settings
from app.services.agents.esclation_analyzer import execute_shadow_override

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.get(
    "/{complaint_id}",
    summary="Get a complaint with all pipeline outputs",
)
async def get_complaint(complaint_id: str):
    """
    Fetch the complete complaint record including all pipeline outputs.

    Returns the complaint with:
    - Original and masked text
    - All agent analysis outputs (category, sentiment, severity, etc.)
    - Draft response and action steps
    - Routing decision and SLA information
    - RBI compliance information
    """
    supabase = get_supabase()

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

    # Remove encrypted original text from response
    # It must never leave the backend unmasked
    complaint.pop("original_text", None)

    return complaint


@router.get(
    "/",
    summary="List all complaints with filters",
)
async def list_complaints(
    route: str = Query(default=None, description="Filter: auto_respond | human_review"),
    category: str = Query(default=None, description="Filter by category"),
    severity: int = Query(default=None, description="Filter by severity 1-5"),
    is_rbi_reportable: bool = Query(default=None, description="Filter RBI cases only"),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
):
    """
    List complaints with optional filters.
    Used by the dashboard complaint list view.
    """
    supabase = get_supabase()

    query = supabase.table("complaints").select(
        "complaint_id, customer_id, channel, category, compliance_category, "
        "is_rbi_reportable, sentiment, severity, route, status, pipeline_status, "
        "confidence_score, risk_score, sla_hours, rbi_tat_deadline, created_at",
        count="exact"
    )

    if route:
        query = query.eq("route", route)
    if category:
        query = query.eq("category", category)
    if severity:
        query = query.eq("severity", severity)
    if is_rbi_reportable is not None:
        query = query.eq("is_rbi_reportable", is_rbi_reportable)

    result = (
        query
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return {
        "total": result.count,
        "limit": limit,
        "offset": offset,
        "complaints": result.data or [],
    }

def detect_fast_track_tier(text: str) -> tuple[int, str]:
    """
    Rule-Based Fast-Track Tier Detection (No ML)
    """
    if not text:
        return 0, "Standard Route"
        
    text_lower = text.lower()
    
    # Tier 5
    if any(kw in text_lower for kw in ["ombudsman", "rbi complaint", "banking ombudsman"]):
        return 5, "RBI/Ombudsman Escalation"
        
    # Tier 4
    if any(kw in text_lower for kw in ["ceo", "head office", "chairman"]) or re.search(r"\bmd\b", text_lower):
        return 4, "Executive Escalation"
        
    # Tier 3
    if any(kw in text_lower for kw in ["regional office", "regional manager"]):
        return 3, "Regional Escalation"
        
    # Tier 2
    if any(kw in text_lower for kw in ["zonal office", "zone manager"]):
        return 2, "Zonal Escalation"
        
    # Tier 1
    # 1. Branch code pattern (e.g., "BR_MH_001")
    if re.search(r"br_[a-z]{2}_\d{3}", text_lower):
        return 1, "Branch Code Detected"
        
    # 2. "branch manager", "branch staff" + negative sentiment
    negative_words = [
        "worst", "bad", "terrible", "frustrated", "angry", "pathetic", 
        "useless", "fraud", "cheat", "scam", "unprofessional", "rude", "poor"
    ]
    has_branch_kw = any(kw in text_lower for kw in ["branch manager", "branch staff"])
    has_negative = any(kw in text_lower for kw in negative_words)
    
    if has_branch_kw and has_negative:
        return 1, "Branch Staff Negative Sentiment"
        
    return 0, "Standard Route"


@router.post(
    "/submit",
    response_model=ComplaintSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a customer complaint",
)
@limiter.limit("10/minute")
async def submit_complaint(
    request: Request,
    complaint_text: str = Form(...),
    channel: str = Form(...),
    customer_id: str = Form(...),
    image: Optional[UploadFile] = File(None),
    x_idempotency_key: str = Header(
        ...,
        description="A UUID generated by the frontend to prevent duplicate submissions"
    ),
):
    """
    Submit a complaint with optional image attachment.

    Required header: X-Idempotency-Key (UUID generated by frontend)
    Optional header: X-API-Key (for auth)

    Returns complaint_id immediately.
    Frontend then calls:
      1. POST /api/v1/pipeline/run/{complaint_id} to start pipeline
      2. GET  /api/v1/pipeline/stream/{complaint_id} for live updates
    """
    settings = get_settings()

    # ── Idempotency check ─────────────────────────────────────────────────
    idempotency_key = x_idempotency_key

    # Returns cached response if key already processed, raises 202 if processing
    cached_response = await check_idempotency(idempotency_key)
    if cached_response:
        return cached_response

    # ── Generate complaint ID ─────────────────────────────────────────────
    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"

    # ── Image processing ──────────────────────────────────────────────────
    image_url = None
    extraction_method = None
    extracted_image_text = None
    merged_text = complaint_text  # default: no image

    if image is not None:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {image.content_type}."
            )

        file_bytes = await image.read()
        max_bytes = settings.max_file_size_mb * 1024 * 1024

        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max {settings.max_file_size_mb}MB."
            )

        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        try:
            image_result = process_image_attachment(
                file_bytes=file_bytes,
                filename=image.filename or "attachment.jpg",
                complaint_text=complaint_text,
            )
            image_url = image_result["image_url"]
            extraction_method = image_result["extraction_method"]
            extracted_image_text = image_result["extracted_image_text"]
            merged_text = image_result["merged_text"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Image processing failed: {str(e)}"
            )

    # ── Fast-Track Tier Detection (Rule-Based) ────────────────────────────
    initial_tier, fast_track_reason = detect_fast_track_tier(merged_text)

    # ── Create complaint record in Supabase ───────────────────────────────
    supabase = get_supabase()

    complaint_record = {
        # ── Identity ──────────────────────────────────────────────────────
        "complaint_id":             complaint_id,
        "customer_id":              customer_id,
        "channel":                  channel,
        # ── Text ──────────────────────────────────────────────────────────
        "original_text":            complaint_text,
        "merged_text":              merged_text,
        "image_url":                image_url,
        "extraction_method":        extraction_method,
        # ── Pipeline state ────────────────────────────────────────────────
        "pipeline_status":          "pending",
        "status":                   "pending",
        # ── Tier routing (pre-pipeline defaults) ──────────────────────────
        # initial_tier may be 0 (standard route) — keep original for audit,
        # but current_tier and assigned_tier must be >= 1 so queue queries work.
        "initial_tier":             initial_tier,
        "current_tier":             max(initial_tier, 1),
        "assigned_tier":            max(initial_tier, 1),
        "max_tier_reached":         initial_tier,
        "total_escalations_count":  0,
        "escalation_count":         0,
        "escalation_path":          [],
        "is_escalating":            False,
        "escalation_loop_detected": False,
        "tier_locked":              False,
        "shadow_overridden":        False,
        "is_duplicate":             False,
        "is_rbi_reportable":        False,
        "rbi_reportable":           False,
        # ── NOT NULL jsonb columns (must be present or Supabase rejects) ──
        "action_steps":             [],
        "grounding_warnings":       [],
        "missing_info_indicators":  [],
        "context_documents":        [],
    }

    try:
        supabase.table("complaints").insert(complaint_record).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create complaint record: {str(e)}"
        )

    # ── Store idempotency key ─────────────────────────────────────────────
    await store_idempotency_key(idempotency_key, complaint_id)

    # ── Build response ────────────────────────────────────────────────────
    return ComplaintSubmitResponse(
        complaint_id=complaint_id,
        complaint_text=complaint_text,
        channel=channel,
        has_image=image is not None,
        image_url=image_url,
        extraction_method=extraction_method,
        extracted_image_text=extracted_image_text,
        merged_text=merged_text,
        status="pending",
        message=(
            f"Complaint {complaint_id} created. "
            f"Start pipeline: POST /api/v1/pipeline/run/{complaint_id}"
        )
    )


@router.post(
    "/{complaint_id}/shadow-override",
    summary="Shadow mode auto-send ko override karo",
)
async def shadow_override(
    complaint_id: str,
    agent_id: str = Body(...),
    corrected_response: str = Body(...),
    override_reason: str = Body(...),
):
    """
    Shadow mode mein human agent 1 hour ke andar override kar sakta hai.

    Kab use karo:
    - Auto-sent response mein kuch galat tha
    - Customer ko corrected response chahiye

    1 hour ke baad override window close ho jaata hai.
    """
    from app.services.agents.esclation_analyzer import execute_shadow_override

    try:
        result = execute_shadow_override(
            complaint_id=complaint_id,
            agent_id=agent_id,
            corrected_response=corrected_response,
            override_reason=override_reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{complaint_id}/escalation-status",
    summary="Get auto-escalation status for a complaint",
)
async def get_escalation_status(complaint_id: str):
    """
    Returns the current auto-escalation state for a complaint.

    Includes:
      - is_escalating        : bool — is a Route 3 loop currently running?
      - current_tier         : int  — where the complaint sits right now
      - escalation_count     : int  — how many tier hops have occurred
      - escalation_path      : list — e.g. [1, 2, 3]
      - max_tier_reached     : int  — highest tier the system has tried
      - last_escalation_at   : ISO datetime
      - escalation_loop_detected : bool
      - escalation_history   : list — full audit trail from complaint_escalation_history
    """
    import logging

    from app.db.supabase_client import get_supabase

    logger = logging.getLogger(__name__)
    supabase = get_supabase()

    def _project_history_row(h: dict) -> dict:
        return {
            "from_tier": h.get("from_tier"),
            "to_tier": h.get("to_tier"),
            "escalation_reason": h.get("escalation_reason"),
            "confidence_before": h.get("confidence_before"),
            "escalation_decision_reasoning": h.get("escalation_decision_reasoning"),
            "signals_detected": h.get("signals_detected"),
            "escalated_at": h.get("escalated_at"),
            "status": h.get("status"),
        }

    # Use select("*") so partial migrations (missing one column) don't break PostgREST.
    try:
        c_result = (
            supabase.table("complaints")
            .select("*")
            .eq("complaint_id", complaint_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("escalation-status: complaints query failed for %s", complaint_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load complaint: {exc!s}",
        ) from exc

    if not c_result.data:
        raise HTTPException(status_code=404, detail=f"Complaint {complaint_id} not found.")

    row = c_result.data[0]
    row.pop("original_text", None)

    escalation_history: list = []
    try:
        h_result = (
            supabase.table("complaint_escalation_history")
            .select("*")
            .eq("complaint_id", complaint_id)
            .order("escalated_at", desc=False)
            .execute()
        )
        for h in h_result.data or []:
            escalation_history.append(_project_history_row(h))
    except Exception as exc:
        # Table missing, RLS, or schema drift — still return complaint tier snapshot
        logger.warning(
            "escalation-status: complaint_escalation_history unavailable for %s: %s",
            complaint_id,
            exc,
        )

    esc_path = row.get("escalation_path")
    if esc_path is None:
        escalation_path: list = []
    elif isinstance(esc_path, list):
        escalation_path = esc_path
    else:
        escalation_path = list(esc_path) if esc_path else []

    current_tier = row.get("current_tier")
    if current_tier is None:
        current_tier = row.get("initial_tier")

    next_action = "idle"
    if row.get("is_escalating"):
        next_action = f"attempting_resolution_at_tier_{current_tier}"
    elif row.get("escalation_count", 0) > 0:
        next_action = "escalation_complete"

    return {
        "complaint_id": complaint_id,
        "is_escalating": bool(row.get("is_escalating", False)),
        "current_tier": current_tier,
        "escalation_count": int(row.get("escalation_count") or 0),
        "escalation_path": escalation_path,
        "max_tier_reached": int(row.get("max_tier_reached") or 0),
        "last_escalation_at": row.get("last_escalation_at"),
        "escalation_loop_detected": bool(row.get("escalation_loop_detected", False)),
        "next_action": next_action,
        "escalation_history": escalation_history,
    }