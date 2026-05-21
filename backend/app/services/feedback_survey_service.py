"""
Feedback Survey Service — dispatch CSAT survey to customer after resolution.

Called from:
  - agent_action_service.handle_accept()   (ACCEPT action)
  - agent_action_service.handle_edit()     (EDIT action)
  - feedback routes trigger_csat_survey()  (manual trigger from dashboard)

Channel routing:
  web       → extract email from original_text → send survey email
  email     → customer_id IS the email address → send survey email
  whatsapp  → customer_id IS the WhatsApp number → send survey WhatsApp
  other     → log and skip (no delivery mechanism)
"""

import logging

logger = logging.getLogger(__name__)


def send_feedback_survey(
    complaint_id: str,
    channel: str,
    customer_id: str,
    original_text: str = "",
) -> None:
    """
    Send a CSAT survey to the customer via their complaint channel.

    Best-effort: never raises — exceptions are caught and logged so they
    cannot block the complaint resolution flow.
    """
    try:
        _dispatch(complaint_id, channel, customer_id, original_text)
    except Exception as exc:
        logger.error("[SURVEY] Unexpected error for %s: %s", complaint_id, exc)


def _dispatch(
    complaint_id: str,
    channel: str,
    customer_id: str,
    original_text: str,
) -> None:
    if channel == "whatsapp":
        to = customer_id if customer_id.startswith("whatsapp:") else f"whatsapp:{customer_id}"
        from app.services.whatsapp_service import send_feedback_survey_whatsapp
        sent = send_feedback_survey_whatsapp(to, complaint_id, customer_id)
        logger.info("[SURVEY] WhatsApp %s for %s → %s", "sent" if sent else "failed", complaint_id, to)

    elif channel == "email":
        from app.services.email_service import send_feedback_survey_email
        sent = send_feedback_survey_email(customer_id, complaint_id, customer_id)
        logger.info("[SURVEY] Email %s for %s → %s", "sent" if sent else "failed", complaint_id, customer_id)

    elif channel == "web":
        from app.services.email_service import extract_email_from_web_text, send_feedback_survey_email
        email = extract_email_from_web_text(original_text)
        if email:
            sent = send_feedback_survey_email(email, complaint_id, email)
            logger.info("[SURVEY] Web→Email %s for %s → %s", "sent" if sent else "failed", complaint_id, email)
        else:
            logger.warning(
                "[SURVEY] Web complaint %s: no email found in original_text — survey not sent",
                complaint_id,
            )
    else:
        logger.info(
            "[SURVEY] Channel %r has no delivery mechanism — skipping survey for %s",
            channel, complaint_id,
        )
