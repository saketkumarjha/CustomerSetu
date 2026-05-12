"""
WhatsApp Service — Twilio send helper + RAG instant reply logic.

This module lives inside the backend package so it can be imported
by both channels.py (webhook) and agent_action_service.py (reply on action).
"""

import uuid
import logging

logger = logging.getLogger(__name__)

# ── Twilio client (lazy) ──────────────────────────────────────────────────────

_twilio_client = None


def _get_twilio_client():
    global _twilio_client
    if _twilio_client is None:
        try:
            from twilio.rest import Client
            from app.core.config import get_settings
            s = get_settings()
            if not s.twilio_account_sid or not s.twilio_auth_token:
                raise ValueError("Twilio credentials not set in .env")
            _twilio_client = Client(s.twilio_account_sid, s.twilio_auth_token)
        except ImportError:
            raise RuntimeError("twilio not installed — run: pip install twilio")
    return _twilio_client


def send_whatsapp_reply(to_number: str, message: str) -> bool:
    """
    Send a WhatsApp message via Twilio REST API.
    Called by agent_action_service when channel == 'whatsapp'.
    """
    from app.core.config import get_settings
    s = get_settings()

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
        logger.error("[WHATSAPP] Send failed to %s: %s", to_number, exc)
        return False


# ── Tier detection ────────────────────────────────────────────────────────────

def detect_tier(text: str) -> int:
    """
    Returns 0 for general queries, 1+ for branch/escalation queries.
    Mirrors detect_fast_track_tier() in complaints.py.
    """
    import re
    t = text.lower()

    if any(kw in t for kw in ["ombudsman", "rbi complaint", "banking ombudsman"]):
        return 5
    if any(kw in t for kw in ["ceo", "head office", "chairman"]) or re.search(r"\bmd\b", t):
        return 4
    if any(kw in t for kw in ["regional office", "regional manager"]):
        return 3
    if any(kw in t for kw in ["zonal office", "zone manager"]):
        return 2
    if re.search(r"br_[a-z]{2}_\d{3}", t):
        return 1

    negative = ["worst", "bad", "terrible", "frustrated", "angry", "pathetic",
                "useless", "fraud", "cheat", "scam", "unprofessional", "rude", "poor"]
    if any(kw in t for kw in ["branch manager", "branch staff"]) and \
       any(kw in t for kw in negative):
        return 1

    return 0


# ── Instant RAG reply (Tier 0) ────────────────────────────────────────────────

def instant_rag_reply(message_text: str) -> str:
    """
    Classify → RAG retrieve → GPT-4o draft → return reply string.
    Runs synchronously; wrap with asyncio.to_thread() from async context.
    """
    from openai import OpenAI
    from app.core.config import get_settings
    from app.services.agents.fanout_agents import _classify_sync
    from app.services.agents.rag_agent import retrieve_context

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # Classify
    try:
        cls = _classify_sync(message_text)
        category = cls.get("category", "General Banking")
    except Exception:
        category = "General Banking"

    # RAG
    try:
        rag = retrieve_context(masked_text=message_text, category=category, n=3)
        docs = rag.get("documents", [])
    except Exception:
        docs = []

    kb_context = "\n\n".join(
        f"[KB {i+1}] {d['resolution_text'][:400]}" for i, d in enumerate(docs)
    ) if docs else "No specific KB entry found."

    system_prompt = (
        "You are a helpful customer service agent for Union Bank of India. "
        "Reply to the customer's WhatsApp message in max 3 sentences. "
        "Use the knowledge base context to answer accurately. "
        "If you cannot answer from context, say you will escalate to a specialist. "
        "Do NOT invent account numbers, transaction IDs, or amounts. "
        "Be warm and professional."
    )
    user_prompt = (
        f"Customer message: {message_text}\n\n"
        f"Knowledge base context:\n{kb_context}\n\n"
        "Write a concise WhatsApp reply:"
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
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("[WHATSAPP] RAG reply generation failed: %s", exc)
        return (
            "Thank you for contacting Union Bank of India. "
            "Our team will assist you shortly. "
            "For urgent help, call 1800-22-2244."
        )


# ── Save complaint to DB ──────────────────────────────────────────────────────

def save_whatsapp_complaint(customer_number: str, message_text: str, tier: int) -> str:
    """Insert a WhatsApp complaint into the DB and return complaint_id."""
    from app.db.supabase_client import get_supabase
    supabase = get_supabase()

    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
    supabase.table("complaints").insert({
        "complaint_id":             complaint_id,
        "customer_id":              customer_number,
        "channel":                  "whatsapp",
        "original_text":            message_text,
        "merged_text":              message_text,
        "pipeline_status":          "pending",
        "status":                   "pending",
        "initial_tier":             tier,
        "current_tier":             tier,
        "assigned_tier":            max(tier, 1),
        "max_tier_reached":         tier,
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
    }).execute()
    return complaint_id
