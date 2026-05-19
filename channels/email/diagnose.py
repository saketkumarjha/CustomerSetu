"""
Email channel end-to-end diagnostic.

Run from any directory:
    python channels/email/diagnose.py

Checks (in order):
  1. .env loaded correctly
  2. Gmail IMAP connection
  3. Gmail SMTP connection + test send
  4. Backend reachability
  5. Backend SMTP config actually loaded
  6. Recent complaints — what routes they took (AUTO fires email; others don't)
"""

import os
import sys
import smtplib
import imaplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Force UTF-8 output on Windows so unicode chars in messages don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

GMAIL_USER        = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
BACKEND_URL       = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1/complaints/submit")
PIPELINE_BASE_URL = os.getenv("PIPELINE_BASE_URL", "http://127.0.0.1:8000/api/v1/pipeline/run")
API_KEY           = os.getenv("API_KEY")

# Derive base from BACKEND_URL  e.g. http://127.0.0.1:8000
_parts = BACKEND_URL.split("/api/")
BACKEND_BASE = _parts[0] if len(_parts) > 1 else "http://127.0.0.1:8000"


def _ok(msg):   print(f"  [OK]   {msg}")
def _fail(msg): print(f"  [FAIL] {msg}")
def _warn(msg): print(f"  [WARN] {msg}")
def _info(msg): print(f"  [INFO] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. .env values
# ─────────────────────────────────────────────────────────────────────────────
def check_env():
    print("\n[1] Environment variables")
    ok = True

    if GMAIL_USER:
        _ok(f"GMAIL_USER = {GMAIL_USER}")
    else:
        _fail("GMAIL_USER not set"); ok = False

    if GMAIL_APP_PASSWORD and GMAIL_APP_PASSWORD != "your_gmail_app_password_here":
        _ok(f"GMAIL_APP_PASSWORD = {'*' * len(GMAIL_APP_PASSWORD)} ({len(GMAIL_APP_PASSWORD)} chars)")
        if len(GMAIL_APP_PASSWORD) != 16:
            _warn(f"Expected 16 chars; got {len(GMAIL_APP_PASSWORD)} — remove any spaces")
    else:
        _fail("GMAIL_APP_PASSWORD is placeholder or missing"); ok = False

    if API_KEY:
        _ok(f"API_KEY = {API_KEY[:8]}...")
    else:
        _fail("API_KEY not set"); ok = False

    _info(f"BACKEND_URL       = {BACKEND_URL}")
    _info(f"PIPELINE_BASE_URL = {PIPELINE_BASE_URL}")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 2. Gmail IMAP (read inbox)
# ─────────────────────────────────────────────────────────────────────────────
def check_imap():
    print("\n[2] Gmail IMAP (inbox read)")
    try:
        conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        conn.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        conn.select("INBOX")
        _, data = conn.search(None, "UNSEEN")
        unseen = len(data[0].split()) if data[0] else 0
        conn.logout()
        _ok(f"IMAP login OK — {unseen} unread email(s) in inbox")
        return True
    except imaplib.IMAP4.error as e:
        _fail(f"IMAP auth failed: {e}")
        _info("Check: Gmail IMAP enabled at mail.google.com → Settings → See all → Forwarding/IMAP")
        _info("Check: App password matches the one generated at myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        _fail(f"IMAP error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Gmail SMTP (send test email to self)
# ─────────────────────────────────────────────────────────────────────────────
def check_smtp():
    print(f"\n[3] Gmail SMTP (send test to {GMAIL_USER})")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[DIAG] UBI Email Channel Test"
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg.attach(MIMEText(
        "This is an automated diagnostic test.\n"
        "If you received this, SMTP outbound is working correctly.",
        "plain", "utf-8",
    ))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        _ok(f"SMTP send OK — check inbox of {GMAIL_USER} for the test email")
        return True
    except smtplib.SMTPAuthenticationError as e:
        _fail(f"SMTP auth failed: {e}")
        _info("Same app password is used for both IMAP and SMTP")
        return False
    except Exception as e:
        _fail(f"SMTP error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Backend reachability
# ─────────────────────────────────────────────────────────────────────────────
def check_backend():
    print(f"\n[4] Backend reachability ({BACKEND_BASE})")
    try:
        r = requests.get(f"{BACKEND_BASE}/health", timeout=5)
        _ok(f"GET /health → {r.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        pass
    try:
        r = requests.get(f"{BACKEND_BASE}/docs", timeout=5)
        _ok(f"Backend reachable (GET /docs → {r.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        _fail(f"Cannot reach {BACKEND_BASE} — is FastAPI running?")
        _info("Start it with: cd backend && uvicorn app.main:app --reload")
        return False
    except Exception as e:
        _fail(f"Backend error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 5. Backend SMTP config loaded
# ─────────────────────────────────────────────────────────────────────────────
def check_backend_smtp_config():
    print(f"\n[5] Backend SMTP config (via debug endpoint)")
    url = f"{BACKEND_BASE}/api/v1/debug/email-config"
    try:
        r = requests.get(url, headers={"X-API-Key": API_KEY}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("smtp_user"):
                _ok(f"smtp_user   = {data['smtp_user']}")
                _ok(f"smtp_host   = {data.get('smtp_host')}")
                _ok(f"smtp_port   = {data.get('smtp_port')}")
                _info(f"smtp_password loaded: {data.get('smtp_password_set')}")
                return True
            else:
                _fail("smtp_user is empty — SMTP_USER not loading from backend .env")
                return False
        elif r.status_code == 404:
            _warn("Debug endpoint not yet added to backend (step 6 below will add it)")
            return None
        else:
            _warn(f"Debug endpoint returned {r.status_code}: {r.text[:100]}")
            return None
    except Exception as e:
        _warn(f"Could not reach debug endpoint: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Recent complaint routes (only AUTO → email is sent)
# ─────────────────────────────────────────────────────────────────────────────
def check_complaint_routes():
    print(f"\n[6] Recent email complaints and their pipeline routes")
    url = f"{BACKEND_BASE}/api/v1/complaints/"
    try:
        r = requests.get(
            url,
            headers={"X-API-Key": API_KEY},
            params={"limit": 10},
            timeout=5,
        )
        if r.status_code != 200:
            _warn(f"Could not list complaints: {r.status_code}")
            return

        complaints = r.json().get("complaints", [])
        email_complaints = [c for c in complaints if c.get("channel") == "email"]

        if not email_complaints:
            _warn("No email complaints found yet — send a test email first")
            return

        auto_count    = 0
        non_auto      = []
        for c in email_complaints:
            route  = c.get("route") or "not_set"
            status = c.get("status") or "?"
            conf   = c.get("confidence_score")
            conf_s = f"{conf:.2f}" if conf else "none"
            cid    = c.get("complaint_id", "")[:16]

            if route == "AUTO":
                auto_count += 1
                _ok(f"{cid}… route=AUTO  conf={conf_s}  status={status}  ← email SHOULD send")
            else:
                non_auto.append((cid, route, conf_s, status))
                _warn(f"{cid}… route={route:<10} conf={conf_s}  status={status}")

        if non_auto:
            print()
            _info("WHY email is NOT sent for non-AUTO routes:")
            _info("  AUTO   → confidence >= 0.95 → email sent immediately")
            _info("  ESCALATE/HUMAN → complaint goes to human agent queue — no auto-email")
            _info("")
            _info("To get AUTO route: submit a simple, clear complaint for a common")
            _info("category (e.g. 'My ATM card was blocked. Please reactivate it.')")
            _info("Simple complaints with high RAG knowledge-base matches score >= 0.95")

    except Exception as e:
        _warn(f"Could not check routes: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  UBI Email Channel — End-to-End Diagnostic")
    print("=" * 60)

    env_ok     = check_env()
    if not env_ok:
        print("\n[STOP] Fix .env values first, then re-run.\n")
        sys.exit(1)

    imap_ok    = check_imap()
    smtp_ok    = check_smtp()
    backend_ok = check_backend()

    if backend_ok:
        check_backend_smtp_config()
        check_complaint_routes()

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  .env values   : {'PASS' if env_ok else 'FAIL'}")
    print(f"  IMAP login    : {'PASS' if imap_ok else 'FAIL'}")
    print(f"  SMTP send     : {'PASS' if smtp_ok else 'FAIL'}")
    print(f"  Backend alive : {'PASS' if backend_ok else 'FAIL'}")

    if imap_ok and smtp_ok and backend_ok:
        print()
        print("  Gmail creds and backend are all OK.")
        print("  If still no email — check complaint routes above (need AUTO).")
    else:
        print()
        print("  Fix the failures above and re-run.")
    print()


if __name__ == "__main__":
    main()
