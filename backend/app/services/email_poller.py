"""
Email IMAP Poller — async background task for inbound email processing.

Connects to Gmail IMAP, polls INBOX every `poll_interval_seconds` for UNSEEN
messages, dispatches each one to the email channel handlers, and marks them as
READ so they're never processed twice.

Lifecycle:
  - Started as asyncio.Task inside FastAPI's lifespan (startup).
  - Cancelled cleanly on shutdown (FastAPI sends CancelledError).
  - Reconnects automatically on connection drops with exponential back-off.

Required env vars (same as outbound SMTP):
  SMTP_USER     — Gmail address (e.g. unionbank.complaints.demo@gmail.com)
  SMTP_PASSWORD — Gmail App Password (16-char, no spaces)

Optional env vars:
  IMAP_HOST                  — default: imap.gmail.com
  IMAP_PORT                  — default: 993
  POLL_INTERVAL_SECONDS      — default: 30
  ENABLE_EMAIL_POLLER        — set to "false" to disable (default: true)
"""

import asyncio
import email
import imaplib
import logging
from email.header import decode_header as _decode_header

logger = logging.getLogger(__name__)


# ── Header / body helpers ─────────────────────────────────────────────────────

def _decode_str(raw) -> str:
    """Decode an RFC 2047-encoded email header value to plain unicode."""
    if raw is None:
        return ""
    parts = _decode_header(raw)
    chunks = []
    for part, charset in parts:
        if isinstance(part, bytes):
            chunks.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            chunks.append(part)
    return " ".join(chunks).strip()


def _extract_body(msg: email.message.Message) -> str:
    """Return the plain-text body of a (possibly multipart) email."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                cd = part.get("Content-Disposition", "")
                if "attachment" in cd:
                    continue
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def _bare_address(raw: str) -> str:
    """Extract the bare email address from a 'Display Name <addr>' string."""
    raw = raw.strip()
    if "<" in raw and ">" in raw:
        return raw.split("<")[1].split(">")[0].strip()
    return raw


# ── IMAP sync helpers (run inside asyncio.to_thread) ─────────────────────────

def _imap_connect(user: str, password: str, host: str, port: int) -> imaplib.IMAP4_SSL:
    """Open an IMAP SSL connection and login. Raises on failure."""
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(user, password)
    logger.info("[IMAP] Logged in as %s via %s:%d", user, host, port)
    return mail


def _imap_fetch_unseen(mail: imaplib.IMAP4_SSL) -> list[dict]:
    """
    Fetch all UNSEEN messages from INBOX.

    Marks each message as \\Seen *before* returning so a crash during dispatch
    doesn't re-process the same email on the next poll.

    Returns a list of dicts: {sender, subject, body}.
    """
    mail.select("INBOX")
    status, data = mail.search(None, "UNSEEN")
    if status != "OK" or not data or not data[0]:
        return []

    msg_ids = data[0].split()
    logger.info("[IMAP] %d unseen message(s) found", len(msg_ids))

    results = []
    for msg_id in msg_ids:
        try:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            if isinstance(raw, int):
                continue  # flag-only response, skip

            msg = email.message_from_bytes(raw)

            sender  = _bare_address(msg.get("From", ""))
            subject = _decode_str(msg.get("Subject", ""))
            body    = _extract_body(msg)

            # Mark as read immediately — prevents double-processing
            mail.store(msg_id, "+FLAGS", "\\Seen")

            if sender and body.strip():
                results.append({"sender": sender, "subject": subject, "body": body})
            else:
                logger.debug("[IMAP] Skipping message %s — empty sender or body", msg_id)

        except Exception as exc:
            logger.error("[IMAP] Error fetching message %s: %s", msg_id, exc)
            continue

    return results


# ── Async dispatch ────────────────────────────────────────────────────────────

async def _dispatch(sender: str, subject: str, body: str) -> None:
    """Route a single parsed email through the appropriate channel handler."""
    from app.api.v1.routes.channels import _email_general_query, _email_branch_query
    from app.services.whatsapp_service import detect_tier

    full_text = f"Subject: {subject}\n\n{body}".strip() if subject else body.strip()
    tier = detect_tier(full_text)

    logger.info(
        "[IMAP] Dispatching from=%s subject=%r tier=%d",
        sender, subject[:60], tier,
    )

    try:
        if tier == 0:
            await _email_general_query(sender, subject, body.strip())
        else:
            await _email_branch_query(sender, subject, body.strip(), tier)
    except Exception as exc:
        logger.error("[IMAP] Dispatch failed for %s: %s", sender, exc)


# ── Main poller loop ──────────────────────────────────────────────────────────

async def run_email_poller() -> None:
    """
    Main async loop — call this from FastAPI lifespan as:

        task = asyncio.create_task(run_email_poller())

    Cancellation (lifespan shutdown) exits cleanly.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.smtp_user or not settings.smtp_password:
        logger.warning(
            "[IMAP] SMTP_USER / SMTP_PASSWORD not set — email poller disabled. "
            "Set these env vars and restart the app."
        )
        return

    if not settings.enable_email_poller:
        logger.info("[IMAP] Disabled via ENABLE_EMAIL_POLLER=false")
        return

    host     = settings.imap_host
    port     = settings.imap_port
    interval = settings.poll_interval_seconds
    user     = settings.smtp_user
    password = settings.smtp_password

    logger.info(
        "[IMAP] Poller starting | %s | %s:%d | every %ds",
        user, host, port, interval,
    )

    mail: imaplib.IMAP4_SSL | None = None
    failures = 0

    while True:
        try:
            # ── (Re-)connect if needed ────────────────────────────────────────
            if mail is None:
                mail = await asyncio.to_thread(_imap_connect, user, password, host, port)
                failures = 0

            # ── Fetch unseen (blocking I/O → thread pool) ─────────────────────
            messages = await asyncio.to_thread(_imap_fetch_unseen, mail)

            # ── Dispatch each email in the async context ──────────────────────
            for m in messages:
                await _dispatch(m["sender"], m["subject"], m["body"])

            # ── Wait for next poll ────────────────────────────────────────────
            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("[IMAP] Poller shutting down (cancelled)")
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass
            return

        except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError, ConnectionError) as exc:
            failures += 1
            backoff = min(300, interval * failures)   # cap at 5 min
            logger.warning(
                "[IMAP] Connection error (attempt %d), reconnecting in %ds: %s",
                failures, backoff, exc,
            )
            mail = None
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return

        except Exception as exc:
            logger.error("[IMAP] Unexpected error: %s", exc, exc_info=True)
            mail = None
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return
