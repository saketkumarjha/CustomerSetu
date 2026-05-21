"""
Auto Responder — Tier 1 (Full Auto) Only

Responsibility (after Agent 10.5 refactor):
  This file handles ONLY Tier 1 — Full Auto-Send.
  Called when routing_agent.py returns route = "AUTO" (confidence >= 0.95).

  Tier 2 (Shadow Mode)      → Agent 10.5 (escalation_analyzer.py)
  Tier 3 (Human Review)     → Agent 10.5 (escalation_analyzer.py)
  Tier 4 (Priority Human)   → Agent 10.5 (escalation_analyzer.py)

Flow:
  routing_agent.py
      └── route == "AUTO"
              └── execute_auto_response()   ← only entry point now
                      └── format_for_tier()        (ResponseFormatter)
                      └── simulate send to customer
                      └── status: auto_closed
                      └── log to notification_log
                      └── save to fine_tune_dataset
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional

from app.db.supabase_client import get_supabase
from app.services.response_formatter import format_for_tier

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────

SAFE_SENTIMENTS_FOR_AUTO = {"Calm", "Concerned"}

NEVER_AUTO_SEND_CATEGORIES = {
    "UNAUTHORIZED_TRANSACTION_FRAUD",
    "RECOVERY_AGENT_HARASSMENT",
    "UNSOLICITED_CARD_ISSUANCE",
    "MIS_SELLING_OF_PRODUCTS",
    "DELAY_IN_PROPERTY_DOC_RELEASE",
    "CREDIT_BUREAU_MISREPORTING",
}


# ── Main Entry Point ─────────────────────────────────────────────────────────

def execute_auto_response(
    complaint_id: str,
    customer_id: str,
    channel: str,
    draft_response: str,
    tier: str,
    confidence_score: float,
    tier_level: int = 1,
    customer_name: str = "Valued Customer",
    issue_summary: str = "your recent complaint",
    sla_deadline: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict:
    """
    Tier 1 (full_auto) complaints ka auto-response execute karo.

    Called by pipeline ONLY when:
      - routing_agent returned route == "AUTO"
      - confidence_score >= 0.95
      - No override rules triggered

    Args:
        complaint_id    : Unique complaint ID
        customer_id     : Customer identifier
        channel         : "email" | "whatsapp" | "web" | "sms"
        draft_response  : Agent 8 ka generated response (grounding-passed)
        tier            : Expected "full_auto"
        confidence_score: Pipeline confidence (should be >= 0.95)
        tier_level      : Complaint's current tier (1–4, default 1)
        customer_name   : For personalised greeting
        issue_summary   : One-line issue description
        sla_deadline    : ISO datetime for RBI TAT deadline
        scope_id        : Branch/zone ID for specific contact lookup

    Returns:
        action_taken          : "full_auto_sent" | "none"
        sent_to_customer      : bool
        human_notified        : bool (always False for Tier 1)
        status                : "auto_closed" | None
        message               : Human-readable result
        formatted_response    : str — final message that was sent
        escalation_info       : dict — escalation timeline info
        notification_channel  : str
        customer_notified_at  : ISO datetime string
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    if tier != "full_auto":
        return {
            "action_taken":       "none",
            "sent_to_customer":   False,
            "human_notified":     False,
            "status":             None,
            "formatted_response": None,
            "escalation_info":    None,
            "notification_channel": channel,
            "customer_notified_at": None,
            "message": (
                f"Tier '{tier}' is not handled by auto_responder. "
                "Tier 2/3/4 routing is managed by Agent 10.5 (escalation_analyzer)."
            ),
        }

    # ── 1. Format tier-appropriate response ──────────────────────────────────
    fmt_result = format_for_tier(
        draft_response = draft_response,
        tier_level     = tier_level,
        complaint_id   = complaint_id,
        customer_name  = customer_name,
        issue_summary  = issue_summary,
        channel        = channel,
        sla_deadline   = sla_deadline,
        scope_id       = scope_id,
    )
    formatted_response = fmt_result["formatted_response"]
    escalation_info    = fmt_result["escalation_info"]

    # ── 2. Send to customer ───────────────────────────────────────────────────
    _simulate_send_to_customer(
        customer_id    = customer_id,
        channel        = channel,
        draft_response = formatted_response,
        send_type      = "FULL_AUTO",
        complaint_id   = complaint_id,
    )

    # ── 3. DB update — complaint record ──────────────────────────────────────
    db_payload = {
        "status":               "resolved",
        "pipeline_status":      "complete",
        "response_tier":        "full_auto",
        "auto_sent_at":         now.isoformat(),
        "final_response_text":  formatted_response,
        "response_sent_at":     now.isoformat(),
        "response_channel":     channel,
        "tier_resolved_at":     tier_level,
    }
    try:
        supabase.table("complaints").update(db_payload).eq(
            "complaint_id", complaint_id
        ).execute()
    except Exception as exc:
        logger.error("[AUTO] DB update failed for %s: %s", complaint_id, exc)

    # ── 4. notification_log (best-effort) ────────────────────────────────────
    _log_notification(
        complaint_id = complaint_id,
        channel      = channel,
        tier_level   = tier_level,
        confidence   = confidence_score,
        sent_at      = now,
    )

    # ── 5. Save to fine-tune dataset ─────────────────────────────────────────
    _save_auto_response_to_dataset(
        complaint_id   = complaint_id,
        draft_response = draft_response,
        tier           = tier,
        agent_score    = 1.0,
    )

    # ── 6. Send CSAT feedback survey to customer ──────────────────────────────
    try:
        original_text = ""
        if channel == "web":
            row = supabase.table("complaints").select("original_text").eq(
                "complaint_id", complaint_id
            ).execute()
            original_text = (row.data[0].get("original_text") or "") if row.data else ""
        from app.services.feedback_survey_service import send_feedback_survey
        send_feedback_survey(complaint_id, channel, customer_id, original_text)
    except Exception as exc:
        logger.warning("[AUTO] Feedback survey failed for %s: %s", complaint_id, exc)

    return {
        "action_taken":         "full_auto_sent",
        "sent_to_customer":     True,
        "human_notified":       False,
        "status":               "auto_closed",
        "formatted_response":   formatted_response,
        "escalation_info":      escalation_info,
        "notification_channel": channel,
        "customer_notified_at": now.isoformat(),
        "message":              f"Response auto-sent to customer via {channel}.",
    }


# ── Private Helpers ───────────────────────────────────────────────────────────

def _simulate_send_to_customer(
    customer_id: str,
    channel: str,
    draft_response: str,
    send_type: str,
    complaint_id: str,
) -> None:
    """
    Dispatch response to customer.
      email   → Gmail SMTP via customer_id (which IS the email for email channel)
      web     → parse customer email from original_text, send via SMTP
      whatsapp/sms → Twilio (not yet wired — console log)
    """
    if channel == "email":
        _send_email_reply(
            to_email=customer_id,
            complaint_id=complaint_id,
            response_text=draft_response,
            send_type=send_type,
        )
        return

    if channel == "web":
        # Web form embeds the customer email in original_text. Look it up and send.
        try:
            from app.services.email_service import extract_email_from_web_text
            supabase = get_supabase()
            row = supabase.table("complaints").select("original_text").eq("complaint_id", complaint_id).execute()
            original_text = row.data[0].get("original_text", "") if row.data else ""
            customer_email = extract_email_from_web_text(original_text)
            if customer_email:
                _send_email_reply(
                    to_email=customer_email,
                    complaint_id=complaint_id,
                    response_text=draft_response,
                    send_type=send_type,
                )
                return
        except Exception as exc:
            logger.warning("[AUTO] Web email lookup failed for %s: %s", complaint_id, exc)
        # Fall through to console log if email not found
        logger.warning("[AUTO] Web complaint %s: no customer email found — reply not sent", complaint_id)

    gateway = {"whatsapp": "Twilio WhatsApp", "sms": "Twilio SMS"}.get(
        channel, "Web Notification"
    )
    print(f"\n{'='*60}")
    print(f"[AUTO-SEND] Type        : {send_type}")
    print(f"[AUTO-SEND] Complaint   : {complaint_id}")
    print(f"[AUTO-SEND] Customer    : {customer_id}")
    print(f"[AUTO-SEND] Channel     : {channel}")
    print(f"[AUTO-SEND] Preview     : {draft_response[:120]}...")
    print(f"[AUTO-SEND] Gateway     : {gateway} (simulated)")
    print(f"{'='*60}\n")


def _send_email_reply(
    to_email: str,
    complaint_id: str,
    response_text: str,
    send_type: str,
) -> None:
    """
    Send a real email reply to the customer via Gmail SMTP.
    to_email is the customer's address (set by email_poller as customer_id).
    Falls back to console log if SMTP credentials are not configured.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.smtp_user or not settings.smtp_password:
        logger.warning(
            "[EMAIL] SMTP not configured — cannot send reply to %s for %s",
            to_email, complaint_id,
        )
        return

    subject = f"Re: Your Complaint Reference {complaint_id} — Union Bank of India"
    from_addr = settings.email_from_address or settings.smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_email

    msg.attach(MIMEText(response_text, "plain", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(from_addr, to_email, msg.as_string())
        logger.info(
            "[EMAIL] Reply sent to %s | complaint=%s | type=%s",
            to_email, complaint_id, send_type,
        )
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "[EMAIL] SMTP auth failed for %s — check SMTP_USER / SMTP_PASSWORD in .env",
            settings.smtp_user,
        )
    except Exception as exc:
        logger.error("[EMAIL] Failed to send reply to %s: %s", to_email, exc)


def _log_notification(
    complaint_id: str,
    channel: str,
    tier_level: int,
    confidence: float,
    sent_at: datetime,
) -> None:
    """Insert a row into notification_log (best-effort — table may not exist yet)."""
    supabase = get_supabase()
    try:
        supabase.table("notification_log").insert({
            "complaint_id": complaint_id,
            "channel":      channel,
            "status":       "sent",
            "sent_at":      sent_at.isoformat(),
            "tier_level":   tier_level,
            "confidence":   confidence,
        }).execute()
    except Exception as exc:
        logger.debug("[AUTO] notification_log insert failed (table may not exist): %s", exc)


def _save_auto_response_to_dataset(
    complaint_id: str,
    draft_response: str,
    tier: str,
    agent_score: float,
) -> None:
    """
    Save Tier 1 auto-sent responses to fine_tune_dataset.

    agent_score:
      1.0 → full_auto sent (highest confidence, no human correction)
    """
    supabase = get_supabase()
    try:
        complaint = (
            supabase.table("complaints")
            .select("masked_text, original_text, category")
            .eq("complaint_id", complaint_id)
            .execute()
        )
        if complaint.data:
            row = complaint.data[0]
            complaint_text = row.get("masked_text") or row.get("original_text") or ""
            if not complaint_text:
                logger.warning("[DATASET] Skipping fine_tune insert for %s — no complaint text", complaint_id)
                return
            supabase.table("fine_tune_dataset").insert({
                "complaint_id":             complaint_id,
                "complaint_text":           complaint_text,
                "ai_draft":                 draft_response,
                "agent_corrected_response": draft_response,
                "agent_rating":             agent_score,
                "category":                 row.get("category") or "General Banking",
                "exported":                 False,
            }).execute()
    except Exception as exc:
        logger.error("[DATASET] Save failed for %s: %s", complaint_id, exc)
