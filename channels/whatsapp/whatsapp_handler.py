import uuid
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Form, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Twilio client (lazy init) ─────────────────────────────────────────────────

_twilio_client = None


def _get_twilio_client():
    global _twilio_client
    if _twilio_client is None:
        try:
            from twilio.rest import Client
            from app.core.config import get_settings
            s = get_settings()
            if not s.twilio_account_sid or not s.twilio_auth_token:
                raise ValueError("Twilio credentials not configured in .env")
            _twilio_client = Client(s.twilio_account_sid, s.twilio_auth_token)
        except ImportError:
            raise RuntimeError(
                "twilio package not installed. Run: pip install twilio"
            )
    return _twilio_client


# ── Public send function (called by agent_action_service) ─────────────────────

def send_whatsapp_reply(to_number: str, message: str) -> bool:
    """
    Send a WhatsApp message via Twilio.

    Called by agent_action_service when channel == 'whatsapp' and
    the agent clicks ACCEPT or EDIT in the dashboard.

    Args:
        to_number: Customer's WhatsApp number, e.g. "whatsapp:+919876543210"
        message:   The response text to send

    Returns True on success, False on failure (non-blocking).
    """
    from app.core.config import get_settings
    s = get_settings()

    # Ensure number has whatsapp: prefix
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    try:
        client = _get_twilio_client()
        client.messages.create(
            from_=s.twilio_whatsapp_number,
            to=to_number,
            body=message,
        )
        logger.info("[WHATSAPP] Reply sent to %s", to_number)
        return True
    except Exception as exc:
        logger.error("[WHATSAPP] Failed to send reply to %s: %s", to_number, exc)
        return False


# ── Rule-based tier detection ─────────────────────────────────────────────────

def _detect_tier(text: str) -> int:
    """Delegate to the shared detect_tier in whatsapp_service."""
    from app.services.whatsapp_service import detect_tier
    return detect_tier(text)


# ── Instant RAG reply for general queries ─────────────────────────────────────

def _instant_rag_reply(message_text: str) -> dict:
    """
    For Tier-0 (general) queries:
    1. Classify the message using Classification Agent
    2. Retrieve top-3 KB resolutions via RAG
    3. Draft a concise WhatsApp reply using GPT-4o

    Returns a dict with 'reply', 'category', and 'context_documents'
    so callers can persist these alongside the complaint record.

    Runs synchronously (called from a background thread via asyncio.to_thread).
    """
    from openai import OpenAI
    from app.core.config import get_settings
    from app.services.agents.fanout_agents import _classify_sync
    from app.services.agents.rag_agent import retrieve_context

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # Step 1: Classify
    try:
        cls_result = _classify_sync(message_text)
        category = cls_result.get("category", "General Banking")
        category_confidence = cls_result.get("confidence")
    except Exception:
        category = "General Banking"
        category_confidence = None

    # Step 2: RAG retrieval
    try:
        rag = retrieve_context(masked_text=message_text, category=category, n=3)
        docs = rag.get("documents", [])
    except Exception:
        docs = []

    # Step 3: Draft WhatsApp reply
    kb_context = "\n\n".join(
        f"[KB {i+1}] {d['resolution_text'][:400]}"
        for i, d in enumerate(docs)
    ) if docs else "No specific KB entry found."

    system_prompt = (
        "You are a helpful customer service agent for Union Bank of India. "
        "Reply to the customer's WhatsApp message concisely (max 3 sentences). "
        "Use the knowledge base context below to answer. "
        "If you cannot answer from the context, say you will escalate to a specialist. "
        "Do NOT make up account numbers, transaction IDs, or specific amounts. "
        "Write in a warm, professional tone."
    )
    user_prompt = (
        f"Customer message: {message_text}\n\n"
        f"Knowledge base context:\n{kb_context}\n\n"
        "Write a concise WhatsApp reply:"
    )

    fallback_reply = (
        "Thank you for contacting Union Bank of India. "
        "Our team will get back to you shortly. "
        "For urgent queries, call 1800-22-2244."
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("[WHATSAPP] RAG reply generation failed: %s", exc)
        reply = fallback_reply

    return {
        "reply": reply,
        "category": category,
        "category_confidence": category_confidence,
        "context_documents": docs,
    }


# ── Save complaint + trigger pipeline ─────────────────────────────────────────

def _save_and_queue(
    customer_number: str,
    message_text: str,
    tier: int,
    image_url: Optional[str] = None,
) -> str:
    """Insert complaint into DB and return complaint_id."""
    from app.db.supabase_client import get_supabase
    supabase = get_supabase()

    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "complaint_id":            complaint_id,
        "customer_id":             customer_number,
        "channel":                 "whatsapp",
        "original_text":           message_text,
        "merged_text":             message_text,
        "image_url":               image_url,
        "pipeline_status":         "pending",
        "status":                  "pending",
        "initial_tier":            tier,
        "current_tier":            tier,
        "assigned_tier":           tier,
        "max_tier_reached":        tier,
        "total_escalations_count": 0,
        "escalation_count":        0,
        "escalation_path":         [],
        "is_escalating":           False,
        "escalation_loop_detected": False,
        "tier_locked":             False,
        "shadow_overridden":       False,
        "is_duplicate":            False,
        "is_rbi_reportable":       False,
        "rbi_reportable":          False,
        "action_steps":            [],
        "grounding_warnings":      [],
        "missing_info_indicators": [],
        "context_documents":       [],
    }
    supabase.table("complaints").insert(record).execute()
    return complaint_id


async def _run_pipeline_bg(complaint_id: str) -> None:
    """Fire-and-forget pipeline run (reuses channels.py logic)."""
    try:
        from app.services.supervisor.graph import pipeline_graph
        from app.services.supervisor.audit_trail import update_complaint_status
        from app.services.supervisor.event_bus import event_bus
        from app.api.v1.routes.pipeline import _save_pipeline_outputs
        from app.db.supabase_client import get_supabase

        supabase = get_supabase()
        result = supabase.table("complaints").select("*").eq("complaint_id", complaint_id).execute()
        if not result.data:
            return
        complaint = result.data[0]

        event_bus.create_queue(complaint_id)
        await update_complaint_status(complaint_id, "processing")

        from app.services.supervisor.pipeline_state import PipelineState
        _initial_tier = max(complaint.get("initial_tier") or 1, 1)
        initial_state: PipelineState = {
            "complaint_id": complaint_id,
            "customer_id": complaint.get("customer_id", ""),
            "channel": "whatsapp",
            "complaint_text": complaint.get("original_text") or "",
            "merged_text": complaint.get("merged_text") or "",
            "image_url": None, "idempotency_key": None,
            "masked_text": None, "language": None, "pii_entities_found": None,
            "is_duplicate": None, "duplicate_of": None, "duplicate_similarity": None,
            "category": None, "category_confidence": None, "sentiment": None,
            "urgency_score": None, "escalation_flag": None, "compliance_category": None,
            "is_rbi_reportable": None, "rbi_supervisor_override": None,
            "severity": None, "severity_score": None, "severity_breakdown": None,
            "context_documents": [], "draft_response": None, "root_cause": None,
            "action_steps": [], "confidence_score": None, "authority_sufficient": None,
            "grounding_score": None, "grounding_warnings": [], "route": None,
            "risk_score": None, "sla_hours": None, "rbi_tat_deadline": None,
            "routing_reason": None, "current_tier": _initial_tier,
            "assigned_tier": None, "escalation_decision": None,
            "explanation_trace": [], "errors": [],
            "pipeline_status": "started", "current_agent": None,
            "formatted_response": None, "notification_channel": None,
            "customer_notified_at": None, "escalation_info": None,
            "escalation_count": 0, "escalation_path": [], "is_escalating": False,
            "escalation_orchestrator_result": None,
            "tier_level": _initial_tier, "tier_scope": None,
            "tier_contact_info": None, "previous_tier_attempts": None,
            "tier_kb_coverage_score": None, "missing_info_indicators": None,
            "resolution_type": None,
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
        logger.exception("[WHATSAPP] Pipeline failed for %s: %s", complaint_id, exc)
    finally:
        try:
            from app.services.supervisor.event_bus import event_bus
            await event_bus.close(complaint_id)
        except Exception:
            pass


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/webhook",
    summary="Twilio WhatsApp incoming message webhook",
    response_class=PlainTextResponse,
)
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),                            # e.g. "whatsapp:+919876543210"
    Body: str = Form(default=""),                     # message text (empty if image-only)
    NumMedia: Optional[str] = Form(default="0"),
    MediaUrl0: Optional[str] = Form(default=None),    # first attached image URL (if any)
    MediaContentType0: Optional[str] = Form(default=None),
):
    """
    Twilio calls this endpoint for every incoming WhatsApp message.

    Configure in Twilio console:
      Messaging → WhatsApp Sandbox → "When a message comes in"
      → POST https://<your-url>/api/v1/channels/whatsapp/webhook

    Returns TwiML (empty — we reply via REST API, not TwiML).
    """
    customer_number = From  # already has "whatsapp:" prefix from Twilio
    message_text = Body.strip()
    has_media = int(NumMedia or 0) > 0

    # If customer sent only an image with no text, use a placeholder so the
    # complaint is still registered and human agents can view the media URL.
    if not message_text and has_media:
        message_text = f"[Image attachment] {MediaUrl0 or ''}"

    if not message_text:
        return ""

    logger.info("[WHATSAPP] Incoming from %s: %s", customer_number, message_text[:80])

    tier = _detect_tier(message_text)

    if tier == 0:
        # ── GENERAL QUERY: instant RAG reply ──────────────────────────────
        background_tasks.add_task(
            _handle_general_query, customer_number, message_text, MediaUrl0
        )
    else:
        # ── BRANCH-LEVEL QUERY: register + pipeline + ACK ─────────────────
        background_tasks.add_task(
            _handle_branch_query, customer_number, message_text, tier, MediaUrl0
        )

    # Return empty TwiML — actual reply sent via REST API in background
    return ""


async def _handle_general_query(
    customer_number: str, message_text: str, image_url: Optional[str] = None
) -> None:
    """Background task: save general query to DB, generate RAG reply, update record."""
    import datetime
    from app.db.supabase_client import get_supabase

    # 1. Persist to DB immediately so the complaint appears in the dashboard
    complaint_id = _save_and_queue(customer_number, message_text, tier=0, image_url=image_url)
    logger.info("[WHATSAPP] General query registered %s for %s", complaint_id, customer_number)

    fallback = (
        "Thank you for contacting Union Bank of India. "
        "Our team will assist you shortly. Call 1800-22-2244 for urgent help."
    )

    try:
        # 2. Generate RAG reply (returns dict with reply + metadata)
        result = await asyncio.to_thread(_instant_rag_reply, message_text)
        reply = result["reply"]

        # 3. Send reply via WhatsApp
        send_whatsapp_reply(customer_number, reply)
        logger.info("[WHATSAPP] General query answered for %s (%s)", customer_number, complaint_id)

        # 4. Update DB with full resolution details — mirrors _save_pipeline_outputs
        now = datetime.datetime.utcnow().isoformat()
        get_supabase().table("complaints").update({
            "status":               "auto_closed",
            "pipeline_status":      "complete",
            "route":                "AUTO",
            "category":             result["category"],
            "category_confidence":  result["category_confidence"],
            "context_documents":    result["context_documents"],
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
        logger.error("[WHATSAPP] General query handler failed for %s: %s", complaint_id, exc)
        send_whatsapp_reply(customer_number, fallback)
        # Mark the DB record so agents know it needs attention
        try:
            get_supabase().table("complaints").update({
                "pipeline_status": "failed",
                "status":          "pending",
                "route":           "HUMAN",
            }).eq("complaint_id", complaint_id).execute()
        except Exception:
            pass


async def _handle_branch_query(
    customer_number: str, message_text: str, tier: int, image_url: Optional[str] = None
) -> None:
    """Background task: register complaint, run pipeline, send ACK."""
    try:
        complaint_id = _save_and_queue(customer_number, message_text, tier, image_url=image_url)

        # Send acknowledgement immediately
        tier_labels = {
            1: "Branch Level", 2: "Zonal Level", 3: "Regional Level",
            4: "Head Office", 5: "RBI Ombudsman",
        }
        tier_label = tier_labels.get(tier, f"Tier {tier}")
        ack = (
            f"✅ Your complaint has been registered.\n"
            f"Reference: *{complaint_id}*\n"
            f"Level: {tier_label}\n\n"
            f"Our team will review and respond within the SLA window. "
            f"You will receive a reply on this WhatsApp number once resolved."
        )
        send_whatsapp_reply(customer_number, ack)

        # Run full AI pipeline in background
        await _run_pipeline_bg(complaint_id)

    except Exception as exc:
        logger.exception("[WHATSAPP] Branch query handler failed: %s", exc)
        send_whatsapp_reply(
            customer_number,
            "We received your message but encountered an issue registering it. "
            "Please call 1800-22-2244 or visit your nearest branch."
        )
