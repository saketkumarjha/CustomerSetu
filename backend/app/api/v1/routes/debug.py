"""
Debug routes — development only.

Never expose in production (guarded by APP_ENV check).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, HTTPException, Query, status
from app.core.config import get_settings

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
