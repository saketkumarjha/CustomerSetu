"""
Channel Demo Routes — Hackathon prototype endpoints for Twitter and IVR channels.
In production these channels use real external services (Twitter Streaming API,
Exotel/Twilio IVR). For the prototype demo these endpoints simulate the exact
same intake pipeline so judges can trigger complaints from the UI.
Routes:
  POST /api/v1/channels/twitter/demo        — Submit a sample tweet as complaint
  POST /api/v1/channels/ivr/demo            — Submit a sample IVR call as complaint
  GET  /api/v1/channels/ivr/audio/{filename} — Serve pre-generated MP3 audio files
"""
import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from typing import Annotated
from pydantic import BaseModel, Field, BeforeValidator

from app.db.supabase_client import get_supabase

async def _trigger_pipeline_bg(complaint_id: str) -> None:
    """Fire-and-forget: start the AI pipeline for a complaint in the background."""
    try:
        from app.services.supervisor.graph import pipeline_graph
        from app.services.supervisor.pipeline_state import PipelineState
        from app.services.supervisor.audit_trail import update_complaint_status
        from app.services.supervisor.event_bus import event_bus
        from app.api.v1.routes.pipeline import _save_pipeline_outputs

        supabase = get_supabase()
        result = supabase.table("complaints").select("*").eq("complaint_id", complaint_id).execute()
        if not result.data:
            return
        complaint = result.data[0]

        # Use the complaint's initial_tier as the pipeline starting point.
        # Never reset to 0 — tier 0 causes wrong queue assignments and confuses
        # the escalation analyzer's from_tier calculation.
        _initial_tier = max(complaint.get("initial_tier") or 1, 1)

        supabase.table("complaints").update({
            "current_tier": _initial_tier,
            "assigned_tier": _initial_tier,
            "is_escalating": False,
            "escalation_count": 0,
            "escalation_path": [],
            "max_tier_reached": _initial_tier,
            "total_escalations_count": 0,
            "tier_pending_at": None,
            "assigned_agent_id": None,
        }).eq("complaint_id", complaint_id).execute()

        event_bus.create_queue(complaint_id)
        await update_complaint_status(complaint_id, "processing")

        initial_state: PipelineState = {
            "complaint_id": complaint_id,
            "customer_id": complaint.get("customer_id", ""),
            "channel": complaint.get("channel", ""),
            "complaint_text": complaint.get("original_text") or "",
            "merged_text": complaint.get("merged_text") or complaint.get("original_text") or "",
            "image_url": None,
            "idempotency_key": None,
            "masked_text": None, "language": None, "pii_entities_found": None,
            "is_duplicate": None, "duplicate_of": None, "duplicate_similarity": None,
            "category": None, "category_confidence": None, "sentiment": None,
            "urgency_score": None, "escalation_flag": None, "compliance_category": None,
            "is_rbi_reportable": None, "rbi_supervisor_override": None,
            "severity": None, "severity_score": None, "severity_breakdown": None,
            "context_documents": None, "draft_response": None, "root_cause": None,
            "action_steps": None, "confidence_score": None, "authority_sufficient": None,
            "grounding_score": None, "grounding_warnings": None, "route": None,
            "risk_score": None, "sla_hours": None, "rbi_tat_deadline": None,
            "routing_reason": None, "current_tier": _initial_tier, "assigned_tier": None,
            "escalation_decision": None, "explanation_trace": [], "errors": [],
            "pipeline_status": "started", "current_agent": None,
            "formatted_response": None, "notification_channel": None,
            "customer_notified_at": None, "escalation_info": None,
            "escalation_count": 0, "escalation_path": [], "is_escalating": False,
            "escalation_orchestrator_result": None,
            "tier_level": _initial_tier, "tier_scope": None, "tier_contact_info": None,
            "previous_tier_attempts": None, "tier_kb_coverage_score": None,
            "missing_info_indicators": None, "resolution_type": None,
        }

        final_state = await pipeline_graph.ainvoke(initial_state)
        await _save_pipeline_outputs(complaint_id, final_state)
        await event_bus.publish(complaint_id, {
            "event": "pipeline_complete",
            "complaint_id": complaint_id,
            "route": final_state.get("route"),
            "category": final_state.get("category"),
        })
    except Exception as exc:
        print(f"[CHANNELS] Pipeline bg task failed for {complaint_id}: {exc}")
    finally:
        try:
            from app.services.supervisor.event_bus import event_bus
            await event_bus.close(complaint_id)
        except Exception:
            pass

demo_router = APIRouter()    # requires X-API-Key (UI demo endpoints)
webhook_router = APIRouter()  # public, called by external services (Twilio, email poller)

# Backwards-compatible alias used by any code that still imports `channels.router`
router = demo_router

# Path to pre-generated IVR sample MP3 files (generated once by ivr_simulator.py)
SAMPLE_CALLS_DIR = Path(__file__).resolve().parents[5] / "channels" / "ivr" / "sample_calls"

# ── Sample data (mirrors the simulator scripts) ────────────────────────────────

SAMPLE_TWEETS = [
    {
        "index": 0,
        "username": "@rahul_sharma92",
        "text": (
            "@UnionBankOfIndia my UPI payment of ₹15,000 failed but amount got deducted "
            "from my account. Transaction ID: UPI2026050812345. Please help urgently!"
        ),
    },
    {
        "index": 1,
        "username": "@priya_mumbai",
        "text": (
            "@UnionBankOfIndia ATM at Andheri branch swallowed my card and didn't dispense "
            "cash. I've been waiting 3 days for resolution. This is completely unacceptable!"
        ),
    },
    {
        "index": 2,
        "username": "@amit_delhi_ncr",
        "text": (
            "@UnionBankOfIndia my home loan EMI was debited twice this month. Account number "
            "ending 4521. Nobody at customer care is responding. #BankingFail"
        ),
    },
    {
        "index": 3,
        "username": "@sneha_bangalore",
        "text": (
            "@UnionBankOfIndia internet banking is down since yesterday. I can't pay my "
            "credit card bill and the due date is today. Will you waive the late fee?"
        ),
    },
    {
        "index": 4,
        "username": "@vikram_trades",
        "text": (
            "@UnionBankOfIndia FD maturity amount not credited to my account even after "
            "5 days of maturity date. Branch is not giving any clear answer. #UnionBank"
        ),
    },
]

SAMPLE_CALLS = [
    {
        "index": 0,
        "caller": "Rajesh Kumar",
        "customer_id": "CUST-RK-9821",
        "audio_file": "call_1_Rajesh_Kumar.mp3",
        "transcript": (
            "Hello, I am calling to complain about a UPI transaction failure. "
            "Yesterday I tried to transfer fifteen thousand rupees to my friend "
            "using Union Bank mobile app. The amount got deducted from my account "
            "but the recipient never received the money. The transaction ID is "
            "UPI202605081234 5. I have been trying to reach customer care since "
            "morning but no one is picking up. Please resolve this urgently as I "
            "need that money back."
        ),
    },
    {
        "index": 1,
        "caller": "Priya Mehta",
        "customer_id": "CUST-PM-4453",
        "audio_file": "call_2_Priya_Mehta.mp3",
        "transcript": (
            "Hi, I want to register a complaint regarding my credit card. "
            "I received my credit card statement this month and there are two "
            "transactions that I did not make. One is for eight thousand rupees "
            "at an online shopping site and another for three thousand five hundred "
            "at a restaurant in Delhi. I think my card details have been stolen. "
            "Please block my card immediately and initiate a fraud investigation."
        ),
    },
    {
        "index": 2,
        "caller": "Amit Singh",
        "customer_id": "CUST-AS-7732",
        "audio_file": "call_3_Amit_Singh.mp3",
        "transcript": (
            "Good morning. I am calling about my home loan account. "
            "My EMI of thirty two thousand rupees was supposed to be debited "
            "on the fifth of this month but it got debited twice. "
            "Due to this double deduction my account went into negative balance "
            "and I got charged an overdraft fee as well. "
            "I want the extra EMI amount refunded immediately along with "
            "the overdraft charges."
        ),
    },
    {
        "index": 3,
        "caller": "Sunita Rao",
        "customer_id": "CUST-SR-2281",
        "audio_file": "call_4_Sunita_Rao.mp3",
        "transcript": (
            "Hello, I am very frustrated right now. I went to the ATM "
            "at the Koramangala branch in Bangalore this morning to withdraw "
            "ten thousand rupees. The ATM showed transaction successful "
            "and debited the amount from my account but no cash came out. "
            "I have the transaction receipt with me. "
            "I need the money credited back to my account today."
        ),
    },
    {
        "index": 4,
        "caller": "Mohammed Farouk",
        "customer_id": "CUST-MF-6610",
        "audio_file": "call_5_Mohammed_Farouk.mp3",
        "transcript": (
            "I am calling to complain about my fixed deposit. "
            "My FD of five lakh rupees matured on the first of this month. "
            "As per the instructions I gave at the branch, the maturity amount "
            "should have been credited to my savings account automatically. "
            "But it has been seven days and I still have not received the amount. "
            "I am a senior citizen and I depend on this FD interest for my monthly "
            "expenses. Please escalate this matter to a senior manager immediately."
        ),
    },
]


# ── Request / Response models ──────────────────────────────────────────────────

def _int_not_bool(v):
    """Reject bool and non-integer floats; coerce whole-number floats → int."""
    if isinstance(v, bool):
        raise ValueError("Expected an integer, not a boolean")
    if isinstance(v, float):
        if not v.is_integer():
            raise ValueError("Expected an integer value, not a fractional float")
        return int(v)
    return v


class TwitterDemoRequest(BaseModel):
    model_config = {"strict": True}
    tweet_index: Annotated[int, BeforeValidator(_int_not_bool), Field(ge=0, le=4, description="Index of sample tweet (0–4)")]
    auto_run: bool = True


class IVRDemoRequest(BaseModel):
    model_config = {"strict": True}
    call_index: Annotated[int, BeforeValidator(_int_not_bool), Field(ge=0, le=4, description="Index of sample IVR call (0–4)")]
    auto_run: bool = True


class ChannelDemoResponse(BaseModel):
    complaint_id: str
    channel: str
    customer_id: str
    preview: str
    message: str


# ── Helper ─────────────────────────────────────────────────────────────────────

def _insert_complaint(channel: str, customer_id: str, complaint_text: str) -> str:
    """Insert a complaint record directly into Supabase and return complaint_id."""
    supabase = get_supabase()
    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"

    record = {
        "complaint_id": complaint_id,
        "customer_id": customer_id,
        "channel": channel,
        "original_text": complaint_text,
        "merged_text": complaint_text,
        "pipeline_status": "pending",
        "status": "pending",
        "initial_tier": 0,
        "current_tier": 0,
        "max_tier_reached": 0,
        # NOT NULL jsonb columns — must be present or Supabase rejects the insert
        "action_steps": [],
        "grounding_warnings": [],
        "missing_info_indicators": [],
        "context_documents": [],
        "escalation_path": [],
        "is_duplicate": False,
        "is_rbi_reportable": False,
        "rbi_reportable": False,
        "shadow_overridden": False,
        "is_escalating": False,
        "escalation_loop_detected": False,
        "tier_locked": False,
        "escalation_count": 0,
        "total_escalations_count": 0,
    }

    try:
        supabase.table("complaints").insert(record).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save complaint: {str(exc)}",
        )

    return complaint_id


# ── Routes ────────────────────────────────────────────────────────────────────

@demo_router.post(
    "/twitter/demo",
    response_model=ChannelDemoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a tweet complaint (prototype demo)",
)
async def twitter_demo(req: TwitterDemoRequest, background_tasks: BackgroundTasks):
    """
    Prototype demo endpoint — simulates a tweet being picked up by the
    Twitter poller and submitted to the complaint pipeline.

    In production this is replaced by a Tweepy Filtered Stream listener
    monitoring @UnionBankOfIndia mentions in real time.
    """
    tweet = SAMPLE_TWEETS[req.tweet_index]
    complaint_text = f"[Twitter complaint from {tweet['username']}]\n\n{tweet['text']}"

    complaint_id = _insert_complaint(
        channel="twitter",
        customer_id=tweet["username"],
        complaint_text=complaint_text,
    )

    if req.auto_run:
        background_tasks.add_task(_trigger_pipeline_bg, complaint_id)

    return ChannelDemoResponse(
        complaint_id=complaint_id,
        channel="twitter",
        customer_id=tweet["username"],
        preview=tweet["text"][:100],
        message=(
            f"Tweet submitted as {complaint_id}. AI pipeline started."
            if req.auto_run
            else f"Tweet submitted as {complaint_id}. Run pipeline manually."
        ),
    )


@demo_router.post(
    "/ivr/demo",
    response_model=ChannelDemoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate an IVR call complaint (prototype demo)",
)
async def ivr_demo(req: IVRDemoRequest, background_tasks: BackgroundTasks):
    """
    Prototype demo endpoint — simulates an IVR call being transcribed by
    Whisper and submitted to the complaint pipeline.
    """
    call = SAMPLE_CALLS[req.call_index]
    complaint_text = (
        f"[IVR Call from {call['caller']} | Customer ID: {call['customer_id']}]\n\n"
        f"{call['transcript']}"
    )

    complaint_id = _insert_complaint(
        channel="ivr",
        customer_id=call["customer_id"],
        complaint_text=complaint_text,
    )

    if req.auto_run:
        background_tasks.add_task(_trigger_pipeline_bg, complaint_id)

    return ChannelDemoResponse(
        complaint_id=complaint_id,
        channel="ivr",
        customer_id=call["customer_id"],
        preview=call["transcript"][:100],
        message=(
            f"IVR call submitted as {complaint_id}. AI pipeline started."
            if req.auto_run
            else f"IVR call submitted as {complaint_id}. Run pipeline manually."
        ),
    )


@demo_router.get(
    "/ivr/audio/{filename}",
    summary="Serve pre-generated IVR sample audio files",
    responses={
        400: {"description": "Invalid filename (must end with .mp3 and not escape the audio directory)"},
        404: {"description": "Audio file not found — run ivr_simulator.py first"},
    },
)
async def get_ivr_audio(filename: str):
    """
    Serve pre-generated MP3 audio files for IVR demo playback.
    Files are generated once by ivr_simulator.py using OpenAI TTS.
    """
    # Normalise: allow callers to omit the .mp3 extension
    if not filename.endswith(".mp3"):
        filename = filename + ".mp3"

    # Block path traversal — resolve() normalises symlinks and separators
    try:
        audio_path = (SAMPLE_CALLS_DIR / filename).resolve()
        safe_root  = SAMPLE_CALLS_DIR.resolve()
        sep = "/" if "/" in str(safe_root) else "\\"
        if not str(audio_path).startswith(str(safe_root) + sep):
            raise HTTPException(status_code=400, detail="Invalid filename.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio file '{filename}' not found. Run ivr_simulator.py option [6] first to generate audio.",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=filename,
    )


# ── WhatsApp / Twilio Webhook ─────────────────────────────────────────────────

import asyncio as _asyncio
import logging as _logging
from typing import Optional as _Optional

_wa_logger = _logging.getLogger(__name__)

# ── Email Channel ──────────────────────────────────────────────────────────────

_email_logger = _logging.getLogger(__name__ + ".email")


@webhook_router.post(
    "/whatsapp/webhook",
    summary="Twilio WhatsApp incoming message webhook",
    response_class=PlainTextResponse,
    tags=["WhatsApp Channel"],
    responses={
        200: {"description": "Empty TwiML — reply sent asynchronously via Twilio REST API"},
        403: {"description": "Forbidden — invalid Twilio signature (X-Twilio-Signature header required)"},
        422: {"description": "Unprocessable Entity — missing or malformed form fields"},
    },
)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(
        ...,
        min_length=13,
        pattern=r"^whatsapp:\+[0-9]{7,15}$",
        description="Sender's WhatsApp number in Twilio format (e.g. whatsapp:+919876543210)",
    ),
    Body: str = Form(..., min_length=1, description="Message body from the customer"),
    NumMedia: _Optional[str] = Form(default="0", description="Number of media attachments (0 if none)"),
):
    """
    Twilio calls this endpoint for every incoming WhatsApp message.

    Set in Twilio console → Messaging → WhatsApp Sandbox:
      "When a message comes in" → POST https://<ngrok>/api/v1/channels/whatsapp/webhook

    Routing:
      Tier 0 (general query) → instant RAG reply
      Tier 1+ (branch query) → register complaint + ACK + pipeline
    """
    from app.core.config import get_settings as _get_settings
    _settings = _get_settings()

    # Validate Twilio signature to prevent spoofed webhook calls.
    # Skipped when: no auth_token is set, or app is not running in production
    # (dev/testing environments don't send real Twilio signatures).
    if _settings.twilio_auth_token and _settings.app_env == "production":
        try:
            from twilio.request_validator import RequestValidator as _TwilioValidator
            _validator = _TwilioValidator(_settings.twilio_auth_token)
            _sig = request.headers.get("X-Twilio-Signature", "")
            _url = str(request.url)
            _params = dict(await request.form())
            if not _validator.validate(_url, _params, _sig):
                _wa_logger.warning("[WHATSAPP] Rejected request with invalid Twilio signature from %s", request.client)
                return PlainTextResponse("", status_code=403)
        except ImportError:
            _wa_logger.warning("[WHATSAPP] twilio package not installed — skipping signature validation")

    customer_number = From   # "whatsapp:+91XXXXXXXXXX"
    message_text = Body.strip()

    if not message_text:
        return ""

    # Reject obviously synthetic numbers (Schemathesis / test payloads).
    # Real Twilio numbers have at least 10 digits after the country code.
    _digits = customer_number.replace("whatsapp:+", "").replace("+", "")
    if len(_digits) < 10 or not _digits.isdigit():
        _wa_logger.debug("[WHATSAPP] Ignoring synthetic test number: %s", customer_number)
        return ""

    _wa_logger.info("[WHATSAPP] Incoming from %s: %s", customer_number, message_text[:80])

    from app.services.whatsapp_service import detect_tier
    tier = detect_tier(message_text)

    if tier == 0:
        background_tasks.add_task(_wa_general_query, customer_number, message_text)
    else:
        background_tasks.add_task(_wa_branch_query, customer_number, message_text, tier)

    return ""   # empty TwiML — reply sent via REST API


async def _wa_general_query(customer_number: str, message_text: str) -> None:
    """Instant RAG reply for general queries — saves complaint to DB first."""
    import datetime
    from app.services.whatsapp_service import (
        instant_rag_reply, send_whatsapp_reply, save_whatsapp_complaint,
    )

    # Save to DB first so the conversation is always traceable
    complaint_id = save_whatsapp_complaint(customer_number, message_text, tier=0)
    _wa_logger.info("[WHATSAPP] General query registered %s for %s", complaint_id, customer_number)

    _ref_suffix = f"\n\n📋 Reference: *{complaint_id}*\nQuote this for any follow-up."
    fallback = (
        "Thank you for contacting Union Bank of India. "
        "Our team will assist you shortly. Call 1800-22-2244 for urgent help."
        + _ref_suffix
    )
    try:
        raw_reply = await _asyncio.to_thread(instant_rag_reply, message_text)
        reply = raw_reply + _ref_suffix
        send_whatsapp_reply(customer_number, reply)
        _wa_logger.info("[WHATSAPP] General query answered for %s (%s)", customer_number, complaint_id)

        now = datetime.datetime.utcnow().isoformat()
        get_supabase().table("complaints").update({
            "status":               "auto_closed",
            "pipeline_status":      "complete",
            "route":                "AUTO",
            "draft_response":       reply,
            "final_response_text":  reply,
            "response_sent_at":     now,
            "auto_sent_at":         now,
            "response_channel":     "whatsapp",
            "current_tier":         0,
            "assigned_tier":        0,
            "resolution_type":      "auto_rag",
            "is_rbi_reportable":    False,
            "rbi_reportable":       False,
            "escalation_flag":      False,
            "is_escalating":        False,
            "escalation_count":     0,
            "max_tier_reached":     0,
            "total_escalations_count": 0,
        }).eq("complaint_id", complaint_id).execute()

    except Exception as exc:
        _wa_logger.error("[WHATSAPP] General query failed for %s: %s", complaint_id, exc)
        send_whatsapp_reply(customer_number, fallback)
        try:
            get_supabase().table("complaints").update({
                "pipeline_status": "failed",
                "status":          "pending",
                "route":           "HUMAN",
            }).eq("complaint_id", complaint_id).execute()
        except Exception:
            pass


async def _wa_branch_query(customer_number: str, message_text: str, tier: int) -> None:
    """Register complaint, send ACK, run pipeline (if auto-mode enabled)."""
    from app.services.whatsapp_service import save_whatsapp_complaint, send_whatsapp_reply
    from app.api.v1.routes.settings import is_auto_pipeline_enabled
    try:
        complaint_id = save_whatsapp_complaint(customer_number, message_text, tier)

        tier_labels = {
            1: "Branch Level", 2: "Zonal Level", 3: "Regional Level",
            4: "Head Office", 5: "RBI Ombudsman",
        }
        ack = (
            f"✅ Your complaint has been registered.\n"
            f"Reference: *{complaint_id}*\n"
            f"Level: {tier_labels.get(tier, f'Tier {tier}')}\n\n"
            f"Our team will review and respond within the SLA window. "
            f"You will receive a reply on this WhatsApp number once resolved."
        )
        send_whatsapp_reply(customer_number, ack)

        # Run full AI pipeline only when auto-mode is enabled
        if is_auto_pipeline_enabled():
            await _trigger_pipeline_bg(complaint_id)
        else:
            _wa_logger.info("[WHATSAPP] Auto-pipeline OFF — %s queued for manual processing", complaint_id)

    except Exception as exc:
        _wa_logger.exception("[WHATSAPP] Branch query failed: %s", exc)
        from app.services.whatsapp_service import send_whatsapp_reply
        send_whatsapp_reply(
            customer_number,
            "We received your message but encountered an issue registering it. "
            "Please call 1800-22-2244 or visit your nearest branch."
        )


# ── Email Inbound Endpoint ────────────────────────────────────────────────────

@webhook_router.post(
    "/email/inbound",
    summary="Email inbound handler (called by email poller for each new email)",
    response_class=PlainTextResponse,
    tags=["Email Channel"],
)
async def email_inbound(
    background_tasks: BackgroundTasks,
    customer_email: str = Form(
        ...,
        min_length=5,
        pattern=r'^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]{2,}$',
        description="Sender's email address (RFC 5321 format)",
    ),
    subject: str = Form(default="", description="Email subject line"),
    body: str = Form(..., min_length=1, description="Email body text"),
    attachment_url: _Optional[str] = Form(default=None, description="Optional attachment URL"),
):
    """
    Called by the email poller for every unread email in the inbox.

    Flow:
      Tier 0 (general query) → save to DB → instant RAG reply → auto_closed
      Tier 1+ (branch query) → save to DB → ACK email → full pipeline → human review
    """
    if not body.strip():
        return ""

    full_text = f"Subject: {subject}\n\n{body}".strip() if subject else body.strip()
    _email_logger.info("[EMAIL] Incoming from %s: %s", customer_email, full_text[:80])

    from app.services.whatsapp_service import detect_tier
    tier = detect_tier(full_text)

    if tier == 0:
        background_tasks.add_task(
            _email_general_query, customer_email, subject, body.strip(), attachment_url
        )
    else:
        background_tasks.add_task(
            _email_branch_query, customer_email, subject, body.strip(), tier, attachment_url
        )

    return ""


async def _email_general_query(
    customer_email: str,
    subject: str,
    message_text: str,
    attachment_url: _Optional[str] = None,
) -> None:
    """Save general email to DB, generate RAG reply, send email, update DB."""
    import datetime
    from app.db.supabase_client import get_supabase
    from app.services.email_service import (
        save_email_complaint, instant_rag_reply_email, send_email_reply,
    )

    full_text = f"Subject: {subject}\n\n{message_text}" if subject else message_text
    # save_email_complaint uses a synchronous httpx client — must run off the event loop
    complaint_id = await _asyncio.to_thread(
        save_email_complaint, customer_email, subject, full_text, tier=0,
        attachment_url=attachment_url,
    )
    _email_logger.info("[EMAIL] General query registered %s for %s", complaint_id, customer_email)

    _ref_footer = (
        f"\n\n---\n"
        f"Reference ID: {complaint_id}\n"
        f"Please quote this reference number in any follow-up correspondence.\n"
        f"For urgent help, please call 1800-22-2244."
    )

    fallback_body = (
        "Thank you for contacting Union Bank of India.\n\n"
        "We have received your query and our team will assist you shortly."
        + _ref_footer
        + "\n\nRegards,\nUnion Bank of India Customer Care"
    )

    try:
        result = await _asyncio.to_thread(instant_rag_reply_email, full_text)
        # Append reference ID so the customer always has a tracking number
        reply_body = result["reply"] + _ref_footer + "\n\nRegards,\nUnion Bank of India Customer Care"

        reply_subject = (
            f"Re: {subject} [Ref: {complaint_id}]"
            if subject
            else f"Response from Union Bank of India [Ref: {complaint_id}]"
        )
        # send_email_reply is a blocking SMTP call — run off the event loop
        await _asyncio.to_thread(send_email_reply, customer_email, reply_subject, reply_body)
        _email_logger.info("[EMAIL] General query answered for %s (%s)", customer_email, complaint_id)

        now = datetime.datetime.utcnow().isoformat()
        updates = {
            "status":                  "auto_closed",
            "pipeline_status":         "complete",
            "route":                   "AUTO",
            "category":                result["category"],
            "category_confidence":     result["category_confidence"],
            "context_documents":       result["context_documents"],
            "draft_response":          reply_body,
            "final_response_text":     reply_body,
            "response_sent_at":        now,
            "auto_sent_at":            now,
            "response_channel":        "email",
            "current_tier":            0,
            "assigned_tier":           0,
            "resolution_type":         "auto_rag",
            "is_rbi_reportable":       False,
            "rbi_reportable":          False,
            "escalation_flag":         False,
            "is_escalating":           False,
            "escalation_count":        0,
            "max_tier_reached":        0,
            "total_escalations_count": 0,
        }
        await _asyncio.to_thread(
            lambda: get_supabase().table("complaints").update(updates)
                    .eq("complaint_id", complaint_id).execute()
        )

    except Exception as exc:
        _email_logger.error("[EMAIL] General query failed for %s: %s", complaint_id, exc)
        try:
            await _asyncio.to_thread(
                send_email_reply,
                customer_email,
                f"Re: Your Query — Union Bank of India [Ref: {complaint_id}]",
                fallback_body,
            )
        except Exception:
            pass
        try:
            await _asyncio.to_thread(
                lambda: get_supabase().table("complaints").update({
                    "pipeline_status": "failed",
                    "status":          "pending",
                    "route":           "HUMAN",
                }).eq("complaint_id", complaint_id).execute()
            )
        except Exception:
            pass


async def _email_branch_query(
    customer_email: str,
    subject: str,
    message_text: str,
    tier: int,
    attachment_url: _Optional[str] = None,
) -> None:
    """Register email complaint, send ACK email, run full AI pipeline (if auto-mode enabled)."""
    from app.services.email_service import save_email_complaint, send_email_reply
    from app.api.v1.routes.settings import is_auto_pipeline_enabled

    full_text = f"Subject: {subject}\n\n{message_text}" if subject else message_text

    try:
        complaint_id = await _asyncio.to_thread(
            save_email_complaint, customer_email, subject, full_text, tier,
            attachment_url=attachment_url,
        )

        tier_labels = {
            1: "Branch Level", 2: "Zonal Level", 3: "Regional Level",
            4: "Head Office", 5: "RBI Ombudsman",
        }
        tier_label = tier_labels.get(tier, f"Tier {tier}")

        ack_body = (
            f"Dear Customer,\n\n"
            f"Your complaint has been registered successfully.\n\n"
            f"Reference Number: {complaint_id}\n"
            f"Level: {tier_label}\n\n"
            f"Our team will review and respond within the SLA window.\n"
            f"You will receive a reply on this email address once resolved.\n\n"
            f"For urgent queries, call 1800-22-2244.\n\n"
            f"Regards,\nUnion Bank of India Customer Care"
        )
        await _asyncio.to_thread(
            send_email_reply, customer_email, f"Complaint Registered: {complaint_id}", ack_body
        )
        _email_logger.info("[EMAIL] ACK sent for %s to %s", complaint_id, customer_email)

        # Run full AI pipeline only when auto-mode is enabled
        if is_auto_pipeline_enabled():
            await _trigger_pipeline_bg(complaint_id)
        else:
            _email_logger.info("[EMAIL] Auto-pipeline OFF — %s queued for manual processing", complaint_id)

    except Exception as exc:
        _email_logger.exception("[EMAIL] Branch query failed for %s: %s", customer_email, exc)
        try:
            from app.services.email_service import send_email_reply
            await _asyncio.to_thread(
                send_email_reply,
                customer_email,
                "Issue Registering Your Complaint — Union Bank of India",
                (
                    "Dear Customer,\n\n"
                    "We received your email but encountered an issue registering your complaint.\n"
                    "Please call 1800-22-2244 or visit your nearest branch.\n\n"
                    "Regards,\nUnion Bank of India Customer Care"
                ),
            )
        except Exception:
            pass
