"""
Email Service — SMTP outbound + RAG instant reply + DB save for email channel.

Mirrors whatsapp_service.py but for email:
  send_email_reply()         → SMTP dispatch via Gmail
  instant_rag_reply_email()  → classify → RAG → GPT-4o draft (returns dict)
  save_email_complaint()     → Supabase insert
"""

import re
import uuid
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

# Accepts only ASCII-safe RFC 5321 addresses; rejects unicode, whitespace, bare locals.
_VALID_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]{2,}$'
)


def send_email_reply(to_address: str, subject: str, body: str) -> bool:
    """
    Send an email reply via SMTP (Gmail).
    Called by agent_action_service when channel == 'email' and
    the agent clicks ACCEPT or EDIT in the dashboard.
    """
    from app.core.config import get_settings
    s = get_settings()

    if not _VALID_EMAIL_RE.match(to_address):
        logger.warning("[EMAIL] Skipping send — invalid recipient address: %r", to_address)
        return False

    if not s.smtp_user or not s.smtp_password:
        logger.warning("[EMAIL] SMTP credentials not configured — skipping send to %s", to_address)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = s.email_from_address or s.smtp_user
        msg["To"] = to_address
        msg["Subject"] = subject or "Response from Union Bank of India"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(msg["From"], to_address, msg.as_string())

        logger.info("[EMAIL] Reply sent to %s", to_address)
        return True
    except Exception as exc:
        logger.error("[EMAIL] Failed to send to %s: %s", to_address, exc)
        return False


def instant_rag_reply_email(message_text: str) -> dict:
    """
    Classify → RAG retrieve → GPT-4o draft → return dict with reply + metadata.
    Runs synchronously; wrap with asyncio.to_thread() from async context.

    Returns:
        {
          'reply': str,
          'category': str,
          'category_confidence': float | None,
          'context_documents': list,
        }
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
        category_confidence = cls.get("confidence")
    except Exception:
        category = "General Banking"
        category_confidence = None

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
        "Reply to the customer's email professionally (max 5 sentences). "
        "Use the knowledge base context to answer accurately. "
        "If you cannot answer from context, say the matter will be escalated to a specialist. "
        "Do NOT invent account numbers, transaction IDs, or amounts. "
        "Close with 'Regards, Union Bank of India Customer Care'."
    )
    user_prompt = (
        f"Customer email: {message_text}\n\n"
        f"Knowledge base context:\n{kb_context}\n\n"
        "Write a professional email reply:"
    )

    fallback = (
        "Thank you for contacting Union Bank of India.\n\n"
        "We have received your query and our team will get back to you within 24 hours.\n"
        "For urgent assistance, please call 1800-22-2244.\n\n"
        "Regards,\nUnion Bank of India Customer Care"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("[EMAIL] RAG reply generation failed: %s", exc)
        reply = fallback

    return {
        "reply": reply,
        "category": category,
        "category_confidence": category_confidence,
        "context_documents": docs,
    }


def save_email_complaint(
    customer_email: str,
    subject: str,
    message_text: str,
    tier: int,
    attachment_url: Optional[str] = None,
) -> str:
    """Insert an email complaint into the DB and return complaint_id."""
    from app.db.supabase_client import get_supabase
    supabase = get_supabase()

    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
    supabase.table("complaints").insert({
        "complaint_id":             complaint_id,
        "customer_id":              customer_email,
        "channel":                  "email",
        "original_text":            message_text,
        "merged_text":              message_text,
        "image_url":                attachment_url,
        "pipeline_status":          "pending",
        "status":                   "pending",
        "initial_tier":             tier,
        "current_tier":             tier,
        "assigned_tier":            tier,
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
