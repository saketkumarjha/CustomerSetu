"""
Email Poller — Gmail IMAP → Backend Email Inbound Endpoint
===========================================================

Flow:
  Poll Gmail inbox every POLL_INTERVAL seconds for unseen emails
        ↓
  POST /api/v1/channels/email/inbound  (backend handles everything)
        ↓
  ┌─────────────────────────────────────────────────────────────┐
  │  GENERAL QUERY (Tier 0)                                     │
  │  → Saved to DB                                             │
  │  → Classification Agent classifies the message             │
  │  → RAG retrieves top-3 KB resolutions                      │
  │  → GPT-4o drafts a reply                                   │
  │  → Reply sent instantly via SMTP                           │
  │  → DB updated: status=auto_closed, route=AUTO              │
  └─────────────────────────────────────────────────────────────┘
        ↓
  ┌─────────────────────────────────────────────────────────────┐
  │  BRANCH-LEVEL QUERY (Tier 1+)                               │
  │  → Saved to DB                                             │
  │  → Full AI pipeline runs in background when Auto is on else if off then automatically.                    │
  │  → ACK sent to customer: "Registered as CMP-XXXXXXXX"      │
  │  → Human agent reviews in Agent Desk                       │
  │  → Reply sent when agent clicks ACCEPT/EDIT in dashboard   │
  └─────────────────────────────────────────────────────────────┘
"""

import os
import re
import sys
import time
import requests
from imap_tools import MailBox, AND
from dotenv import load_dotenv

# Force UTF-8 output on Windows so unicode chars don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load .env from the same directory as this script
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

GMAIL_USER         = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
INBOUND_URL        = os.getenv("INBOUND_URL")          # http://localhost:8000/api/v1/channels/email/inbound
API_KEY            = os.getenv("API_KEY")
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL_SECONDS", 30))

MAX_BODY_CHARS = 4000

_HTML_TAG_RE  = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s{3,}")

# Senders and subject prefixes to skip — bounce-backs, auto-replies, system mail
_SKIP_SENDERS = re.compile(
    r"^(mailer-daemon|postmaster|noreply|no-reply|auto-reply|"
    r"delivery-status|bounce|mail-daemon)@",
    re.IGNORECASE,
)
_SKIP_SUBJECTS = re.compile(
    r"^(delivery status notification|undelivered mail|mail delivery failed|"
    r"auto(matic)? reply|out of office|automatic response|\[diag\])",
    re.IGNORECASE,
)


def _strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", html)
    text = _WHITESPACE_RE.sub("\n", text)
    return text.strip()


def extract_customer_id(email_from: str) -> str:
    match = re.search(r"[\w.\-+]+@[\w.\-]+", email_from)
    return match.group(0).lower() if match else email_from.strip().lower()


def submit_email(customer_email: str, subject: str, body: str) -> bool:
    """
    POST the email to /api/v1/channels/email/inbound.
    The backend handles tier detection, RAG reply, DB save, and SMTP dispatch.
    Returns True on success, False on failure.
    """
    if not INBOUND_URL:
        print("    [✗] INBOUND_URL not set in .env")
        return False

    headers = {"X-API-Key": API_KEY}
    payload = {
        "customer_email": customer_email,
        "subject":        subject or "",
        "body":           body,
    }

    try:
        resp = requests.post(INBOUND_URL, data=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            print(f"    [✓] Forwarded to backend (tier detection + pipeline will run)")
            return True
        print(f"    [✗] Backend returned {resp.status_code}: {resp.text}")
        return False

    except requests.exceptions.ConnectionError:
        print("    [✗] Cannot reach backend — is it running?")
        return False
    except Exception as e:
        print(f"    [✗] Submit error: {e}")
        return False


def poll_inbox() -> None:
    print(f"[Email Poller] Connecting to Gmail as {GMAIL_USER}...")

    try:
        with MailBox("imap.gmail.com").login(GMAIL_USER, GMAIL_APP_PASSWORD) as mailbox:
            messages = list(mailbox.fetch(AND(seen=False), mark_seen=False))

            if not messages:
                print("[Email Poller] No new emails.")
                return

            for i, msg in enumerate(messages):
                print(f"\n[>>] From: {msg.from_} | Subject: {msg.subject}")

                sender_addr = extract_customer_id(msg.from_)
                subject_str = (msg.subject or "").strip()

                # Skip bounce-backs, delivery failures, and auto-generated system mail
                if _SKIP_SENDERS.match(sender_addr) or _SKIP_SUBJECTS.match(subject_str):
                    print("    [--] Skipped — system/bounce email.")
                    mailbox.flag(msg.uid, ["\\Seen"], True)
                    continue

                # Prefer plain text; fall back to HTML with tags stripped
                if msg.text:
                    raw_body = msg.text
                elif msg.html:
                    raw_body = _strip_html(msg.html)
                else:
                    raw_body = ""

                # Truncate very long emails
                if len(raw_body) > MAX_BODY_CHARS:
                    raw_body = raw_body[:MAX_BODY_CHARS] + "\n[truncated]"

                customer_email = sender_addr
                subject        = subject_str

                ok = submit_email(customer_email, subject, raw_body)

                if ok:
                    # Mark as read so next poll skips this email
                    mailbox.flag(msg.uid, ["\\Seen"], True)
                    print("    [OK] Marked as read.")
                    # Rate-limit guard: only sleep after real submissions
                    time.sleep(7)

    except Exception as e:
        print(f"[Email Poller] Error: {e}")


def main() -> None:
    print(f"[Email Poller] Starting. Polling every {POLL_INTERVAL}s.")
    print(f"[Email Poller] Backend inbound → {INBOUND_URL}\n")

    while True:
        try:
            poll_inbox()
        except Exception as e:
            print(f"[Error] Unexpected: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
