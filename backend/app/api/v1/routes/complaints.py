"""
Complaint Routes — Unified entry point for all complaint operations

Routes:
  POST /api/v1/complaints/submit          — New complaint submission
  GET  /api/v1/complaints/                — List with filters
  GET  /api/v1/complaints/{id}            — Single complaint detail
  POST /api/v1/complaints/{id}/shadow-override — Shadow mode override
"""
import asyncio
import uuid
from fastapi import (
    APIRouter, File, Form, UploadFile,
    HTTPException, status, Request,
    Header, Query, Body, Path
)
from typing import Literal, Optional, Annotated
import re
from functools import lru_cache
from app.models.complaint import ComplaintSubmitResponse
from app.services.image_handler import process_image_attachment
from app.middleware.idempotency import check_idempotency, store_idempotency_key
from app.middleware.rate_limiter import limiter
from app.db.supabase_client import get_supabase
from app.core.config import get_settings
# from app.services.agents.esclation_analyzer import execute_shadow_override

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_CHANNELS = {"web", "email", "whatsapp", "twitter", "ivr", "branch", "mobile"}

MAX_COMPLAINT_TEXT_CHARS = 10_000   # ~2,500 tokens — prevents runaway OpenAI spend
MIN_COMPLAINT_TEXT_CHARS = 10       # rejects one-word garbage submissions
MAX_CUSTOMER_ID_CHARS    = 64


@router.get("/submit", include_in_schema=False)
@router.delete("/submit", include_in_schema=False)
@router.patch("/submit", include_in_schema=False)
@router.put("/submit", include_in_schema=False)
async def _submit_method_not_allowed():
    """Return 405 for non-POST methods on /submit before /{complaint_id} can swallow them."""
    from fastapi.responses import Response
    return Response(status_code=405, headers={"Allow": "POST"})


@router.get(
    "/{complaint_id}",
    summary="Get a complaint with all pipeline outputs",
    responses={404: {"description": "Complaint not found"}},
)
async def get_complaint(complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)")):
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
    complaint.pop("original_text", None)

    return complaint


@router.get(
    "/",
    summary="List all complaints with filters",
    responses={500: {"description": "Database or range query error"}},
)
async def list_complaints(
    route: str = Query(default=None, description="Filter: auto_respond | human_review"),
    category: str = Query(default=None, description="Filter by category"),
    severity: int = Query(default=None, ge=1, le=5, description="Filter by severity 1-5"),
    is_rbi_reportable: Optional[str] = Query(default=None, description="Filter RBI cases only (true/false)", pattern="^(true|false|null)$"),
    limit: int = Query(default=10, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
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
        query = query.eq("is_rbi_reportable", is_rbi_reportable.lower() == "true")

    try:
        result = (
            query
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        # PGRST103 fires when offset exceeds the total row count — return empty page
        code = getattr(exc, "code", None)
        if code == "PGRST103":
            return {"total": 0, "limit": limit, "offset": offset, "complaints": []}
        raise

    return {
        "total": result.count,
        "limit": limit,
        "offset": offset,
        "complaints": result.data or [],
    }


# ── Patterns compiled once ────────────────────────────────────────────────────

def _build_patterns() -> dict:
    return {
        "tier5": re.compile(
            r"\b("
            r"ombudsman|rbi\s+complaint|banking\s+ombudsman|"
            r"rbi\s+grievance|cepd|grievance\s+redressal|"
            r"consumer\s+forum|consumer\s+court|"
            r"banking\s+ombudsman\s+\w+"          # e.g. "banking ombudsman mumbai"
            r")\b",
            re.IGNORECASE,
        ),
        "tier4": re.compile(
            r"\b("
            r"ceo|chairman|head\s+office|managing\s+director|"
            r"general\s+manager|dgm|agm|"
            r"corporate\s+office|national\s+head"
            r")\b"
            r"|\bmd\b",          # standalone MD kept separate to avoid "cmd", "remade" etc.
            re.IGNORECASE,
        ),
        "tier3": re.compile(
            r"\b("
            r"regional\s+(manager|office|head)|"
            r"ro_[a-z]{2,3}"                      # e.g. ro_mh, ro_del
            r")\b",
            re.IGNORECASE,
        ),
        "tier2": re.compile(
            r"\b("
            r"zonal\s+(manager|office|head)|zone\s+manager|"
            r"zo_[a-z]{2,4}|"                     # e.g. zo_north
            r"br_[a-z]{2}_\d{3}"                  # branch code (moved here — zonal owns it)
            r")\b",
            re.IGNORECASE,
        ),
        # Tier 1 sub-signals
        "branch_staff": re.compile(
            r"\b(branch\s+(manager|staff|officer|head|employee))\b",
            re.IGNORECASE,
        ),
        "negative": re.compile(
            r"\b("
            r"worst|bad|terrible|horrible|disgusting|"
            r"frustrated|angry|furious|upset|helpless|"
            r"pathetic|useless|incompetent|negligent|"
            r"fraud|cheated?|scam|fake|"
            r"unprofessional|rude|misbeh[ae]v(ed?|iour)|harass(ed|ment)|"
            r"poor\s+service|no\s+response|ignored|misled"
            r")\b",
            re.IGNORECASE,
        ),
        "repeated_visits": re.compile(
            r"("
            r"visited?\s+\w+\s+\d+\s+times?|"
            r"\d+\s+(times?|visits?)\s+to\s+(the\s+)?branch|"
            r"(multiple|several|many|repeated)\s+(times?|visits?)"
            r")",
            re.IGNORECASE,
        ),
        "high_amount": re.compile(
            r"[₹rs\.]+\s*\d{4,}",   # ₹1000 and above  (₹, Rs, Rs.)
            re.IGNORECASE,
        ),
    }

_PATTERNS = _build_patterns()

# ── Tier labels ───────────────────────────────────────────────────────────────

TIER_LABELS = {
    0: "Standard Route",
    1: "Branch Escalation",
    2: "Zonal Escalation",
    3: "Regional Escalation",
    4: "Executive Escalation",
    5: "RBI/Ombudsman Escalation",
}

# ── Main function ─────────────────────────────────────────────────────────────

def detect_fast_track_tier(text: str) -> tuple[int, str]:
    """
    Rule-based fast-track tier detection.

    Returns (tier: int, label: str).
    Higher tier = higher urgency. First match wins (tiers checked 5 → 0).
    """
    if not text or not text.strip():
        return 0, TIER_LABELS[0]

    t = text.strip()

    if _PATTERNS["tier5"].search(t):
        return 5, TIER_LABELS[5]

    if _PATTERNS["tier4"].search(t):
        return 4, TIER_LABELS[4]

    if _PATTERNS["tier3"].search(t):
        return 3, TIER_LABELS[3]

    if _PATTERNS["tier2"].search(t):
        return 2, TIER_LABELS[2]

    # Tier 1: any ONE of the three signals is enough
    has_branch   = bool(_PATTERNS["branch_staff"].search(t))
    has_negative = bool(_PATTERNS["negative"].search(t))
    has_repeated = bool(_PATTERNS["repeated_visits"].search(t))
    has_amount   = bool(_PATTERNS["high_amount"].search(t))

    if (has_branch and has_negative) or has_repeated or has_amount:
        return 1, TIER_LABELS[1]

    return 0, TIER_LABELS[0]
def _rate_limit_string() -> str:
    from app.core.config import get_settings as _gs
    return f"{_gs().rate_limit_per_minute}/minute"


@router.post(
    "/submit",
    response_model=ComplaintSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a customer complaint",
    responses={
        202: {"description": "Complaint still processing (duplicate idempotency key)"},
        400: {"description": "Invalid input (text too short/long, bad file type, etc.)"},
        429: {
            "description": "Rate limit exceeded — max 10 requests/minute per IP",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                        "example": {"detail": "Rate limit exceeded: 10 per 1 minute. Please retry after the window resets."},
                    }
                }
            },
        },
        500: {"description": "Image processing failed or database insert error"},
    },
)
@limiter.limit(_rate_limit_string)
async def submit_complaint(
    request: Request,
    complaint_text: str = Form(..., min_length=10, max_length=10_000, pattern=r"^[^\x00]*$"),
    channel: Literal["web", "email", "whatsapp", "twitter", "ivr", "branch", "mobile"] = Form(...),
    customer_id: str = Form(..., min_length=1, max_length=64),
    image: Optional[UploadFile] = File(None, description="Optional image file (jpeg, png, webp, gif). Must be a valid file upload, not a string or null."),
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

    complaint_text = complaint_text.strip().replace('\x00', '')
    if len(complaint_text) < MIN_COMPLAINT_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"complaint_text too short (minimum {MIN_COMPLAINT_TEXT_CHARS} characters)."
        )
    if len(complaint_text) > MAX_COMPLAINT_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"complaint_text too long (maximum {MAX_COMPLAINT_TEXT_CHARS} characters)."
        )

    channel = channel.strip().lower()
    if channel not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel '{channel}'. Allowed: {sorted(ALLOWED_CHANNELS)}."
        )

    customer_id = customer_id.strip()
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id cannot be empty."
        )
    if len(customer_id) > MAX_CUSTOMER_ID_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"customer_id too long (maximum {MAX_CUSTOMER_ID_CHARS} characters)."
        )

    idempotency_key = x_idempotency_key

    # Returns:
    #   None        → new key, proceed normally
    #   dict        → cached pipeline result, return immediately as 201
    #   JSONResponse→ 202 still-processing (pass through directly)
    # from fastapi.responses import JSONResponse as _JSONResponse
    idempotency_result = await check_idempotency(idempotency_key)
    if idempotency_result is not None:
        return idempotency_result

    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"

    image_url = None
    extraction_method = None
    extracted_image_text = None
    merged_text = complaint_text  # default: no image

    if image is not None:
        if not image.content_type or image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported file type: '{image.content_type or 'unknown'}'. "
                    f"Accepted: {sorted(ALLOWED_IMAGE_TYPES)}. "
                    f"The 'image' field must be a real file upload (multipart/form-data), not a plain string."
                )
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

    initial_tier, fast_track_reason = detect_fast_track_tier(merged_text)

    supabase = get_supabase()

    complaint_record = {
        "complaint_id":             complaint_id,
        "customer_id":              customer_id,
        "channel":                  channel,
        "original_text":            complaint_text,
        "merged_text":              merged_text,
        "image_url":                image_url,
        "extraction_method":        extraction_method,
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
        "action_steps":             [],
        "grounding_warnings":       [],
        "missing_info_indicators":  [],
        "context_documents":        [],
    }

    try:
        await asyncio.to_thread(
            lambda: supabase.table("complaints").insert(complaint_record).execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create complaint record: {str(e)}"
        )

    # ── Store idempotency key ─────────────────────────────────────────────
    await store_idempotency_key(idempotency_key, complaint_id)

    # ── ACK email for web-channel submissions ─────────────────────────────
    # Parse the customer's email from the complaint text (frontend writes
    # "Email: user@example.com" as a header line) and send an acknowledgement.
    # This is purely informational — does NOT change status.
    if channel == "web":
        try:
            from app.services.email_service import extract_email_from_web_text, send_ack_email
            customer_email = extract_email_from_web_text(complaint_text)
            if customer_email:
                await asyncio.to_thread(send_ack_email, customer_email, complaint_id)
        except Exception as _ack_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[ACK] Failed for %s: %s", complaint_id, _ack_err
            )

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
    responses={
        404: {"description": "Complaint not found"},
        409: {"description": "Complaint not in shadow mode or override window closed"},
        500: {"description": "Unexpected server error"},
    },
)
async def shadow_override(
    complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)"),
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
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=409, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/{complaint_id}/escalation-status",
    summary="Get auto-escalation status for a complaint",
    responses={
        404: {"description": "Complaint not found"},
        500: {"description": "Database error loading complaint or escalation history"},
    },
)
async def get_escalation_status(complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)")):
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