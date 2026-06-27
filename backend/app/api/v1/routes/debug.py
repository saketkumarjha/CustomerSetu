"""
Debug routes — development only.

Never expose in production (guarded by APP_ENV check).
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, HTTPException, Query, status
from app.core.config import get_settings

_debug_logger = logging.getLogger(__name__)

router = APIRouter()


def _require_dev():
    settings = get_settings()
    if settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoints are only available in development mode.",
        )


@router.get(
    "/email-config",
    summary="Check what SMTP settings are loaded",
    tags=["Debug"],
)
def get_email_config():
    """Returns loaded SMTP settings (password masked). Dev only."""
    _require_dev()
    settings = get_settings()
    return {
        "smtp_host":         settings.smtp_host,
        "smtp_port":         settings.smtp_port,
        "smtp_user":         settings.smtp_user,
        "smtp_password_set": bool(settings.smtp_password),
        "email_from_address": settings.email_from_address,
    }


@router.post(
    "/send-test-email",
    summary="Send a test SMTP email to verify credentials",
    tags=["Debug"],
    responses={
        400: {"description": "Missing SMTP config or invalid recipient address"},
        401: {"description": "SMTP authentication failed"},
        403: {"description": "Debug endpoints are only available in development mode"},
    },
)
def send_test_email(
    to: str = Query(
        ...,
        min_length=6,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Recipient email address (e.g. user@example.com)",
    ),
):
    """
    Sends a test email via the configured SMTP credentials.
    Pass ?to=your@email.com
    Dev only.
    """
    _require_dev()

    settings = get_settings()

    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP_USER or SMTP_PASSWORD not configured in backend .env",
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[UBI Debug] SMTP Test Email"
    msg["From"]    = settings.smtp_user
    msg["To"]      = to
    msg.attach(MIMEText(
        "This is a test email sent from the backend debug endpoint.\n"
        "If you received this, SMTP is correctly configured.",
        "plain", "utf-8",
    ))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to, msg.as_string())

        return {
            "sent": True,
            "to": to,
            "from": settings.smtp_user,
            "smtp_host": settings.smtp_host,
        }

    except smtplib.SMTPAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SMTP auth failed: {e}. Check SMTP_USER/SMTP_PASSWORD in backend/.env",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP error: {e}",
        )


@router.post(
    "/relink-cif-backfill",
    summary="Backfill cif_id for email/WhatsApp complaints stuck at identity_status=provisional",
    tags=["Debug"],
)
def relink_cif_backfill():
    """
    Scans complaints where identity_status='provisional', cif_id IS NULL, and
    channel IN ('email', 'whatsapp'). For each, re-runs resolve_identity and
    links the complaint to a CIF. Returns a summary of linked/skipped counts.
    Dev only.
    """
    _require_dev()

    from app.db.supabase_client import get_supabase
    from app.services.identity_service import resolve_identity, link_complaint_to_cif, normalize_phone

    supabase = get_supabase()

    resp = (
        supabase.table("complaints")
        .select("complaint_id, customer_id, channel")
        .eq("identity_status", "provisional")
        .is_("cif_id", "null")
        .in_("channel", ["email", "whatsapp"])
        .execute()
    )
    candidates = resp.data or []

    linked, skipped, errors = [], [], []

    for row in candidates:
        complaint_id = row["complaint_id"]
        customer_id = row["customer_id"]
        channel = row["channel"]

        try:
            if channel == "whatsapp":
                identifier = normalize_phone(customer_id)
            else:
                identifier = customer_id

            result = resolve_identity(channel, identifier)
            if result.get("cif_id"):
                link_complaint_to_cif(complaint_id, result["cif_id"], set_pending=False)
                linked.append({"complaint_id": complaint_id, "cif_id": result["cif_id"], "status": result["status"]})
                _debug_logger.info("[BACKFILL] Linked %s → cif=%s (status=%s)", complaint_id, result["cif_id"], result["status"])
            else:
                skipped.append({"complaint_id": complaint_id, "reason": "no cif_id returned"})
        except Exception as exc:
            _debug_logger.error("[BACKFILL] Failed for %s: %s", complaint_id, exc, exc_info=True)
            errors.append({"complaint_id": complaint_id, "error": str(exc)})

    return {
        "total_candidates": len(candidates),
        "linked": len(linked),
        "skipped": len(skipped),
        "errors": len(errors),
        "details": {"linked": linked, "skipped": skipped, "errors": errors},
    }


@router.post("/backfill-summaries", summary="Backfill complaint_summary for all complaints missing it")
def backfill_complaint_summaries():
    """
    Re-runs generate_complaint_summary for every complaint where complaint_summary is NULL.
    Also marks affected cif_summaries rows as dirty so the scheduler regenerates narratives.
    Safe to call multiple times — skips complaints that already have a summary.
    """
    from app.db.supabase_client import get_supabase
    from app.services.complaint_summary_service import generate_complaint_summary

    supabase = get_supabase()
    resp = (
        supabase.table("complaints")
        .select("complaint_id")
        .is_("complaint_summary", "null")
        .not_.is_("pipeline_status", "null")
        .execute()
    )
    candidates = [r["complaint_id"] for r in (resp.data or [])]

    processed, errors = [], []
    for complaint_id in candidates:
        try:
            generate_complaint_summary(complaint_id)
            processed.append(complaint_id)
            _debug_logger.info("[BACKFILL_SUMMARY] processed %s", complaint_id)
        except Exception as exc:
            _debug_logger.error("[BACKFILL_SUMMARY] failed for %s: %s", complaint_id, exc, exc_info=True)
            errors.append({"complaint_id": complaint_id, "error": str(exc)})

    return {
        "total_candidates": len(candidates),
        "processed": len(processed),
        "errors": len(errors),
        "details": {"processed": processed, "errors": errors},
    }
