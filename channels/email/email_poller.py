import time
import uuid
import requests
from imap_tools import MailBox, AND
from dotenv import load_dotenv
import os

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
BACKEND_URL = os.getenv("BACKEND_URL")
API_KEY = os.getenv("API_KEY")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", 30))


def extract_customer_id(email_from: str) -> str:
    """Extract sender email address to use as customer_id."""
    return email_from.split("<")[-1].replace(">", "").strip()


def build_complaint_text(subject: str, body: str) -> str:
    """Combine subject + body into one complaint_text string."""
    subject_line = f"Subject: {subject}\n\n" if subject else ""
    return f"{subject_line}{body}".strip()


def submit_complaint(complaint_text: str, customer_id: str):
    """
    POST to /api/v1/complaints/submit.

    Important:
    - Uses data= (multipart/form-data), NOT json= — endpoint uses Form(...)
    - X-Idempotency-Key: fresh UUID per submission to prevent duplicates
    - X-API-Key: required by auth middleware
    """
    headers = {
        "X-API-Key": API_KEY,
        "X-Idempotency-Key": str(uuid.uuid4()),
    }

    # Must use data= not json= because endpoint is Form(...) not Body(...)
    payload = {
        "complaint_text": complaint_text,
        "channel": "email",
        "customer_id": customer_id,
    }

    try:
        resp = requests.post(BACKEND_URL, data=payload, headers=headers, timeout=10)

        if resp.status_code == 201:
            data = resp.json()
            print(f"    [✓] Saved as {data['complaint_id']}")
            print(f"    Run pipeline: POST /api/v1/pipeline/run/{data['complaint_id']}")
        elif resp.status_code == 202:
            # Idempotency: already processing (same key seen before — shouldn't happen here)
            print(f"    [~] Already processing: {resp.json()}")
        else:
            print(f"    [✗] Failed ({resp.status_code}): {resp.text}")

    except requests.exceptions.ConnectionError:
        print("    [✗] Cannot reach FastAPI — is it running on port 8000?")
    except Exception as e:
        print(f"    [✗] Error: {e}")


def poll_inbox():
    print(f"[Email Poller] Connecting to Gmail as {GMAIL_USER}...")

    try:
        with MailBox("imap.gmail.com").login(GMAIL_USER, GMAIL_APP_PASSWORD) as mailbox:
            # Fetch only UNSEEN (unread) emails
            messages = list(mailbox.fetch(AND(seen=False)))

            if not messages:
                print("[Email Poller] No new emails.")
                return

            for msg in messages:
                print(f"\n[→] New email from: {msg.from_} | Subject: {msg.subject}")

                body = msg.text or msg.html or ""
                complaint_text = build_complaint_text(msg.subject, body)
                customer_id = extract_customer_id(msg.from_)

                submit_complaint(complaint_text, customer_id)

                # Mark as read so next poll skips this email
                mailbox.flag(msg.uid, ["\\Seen"], True)
                print(f"    [✓] Marked as read.")

    except Exception as e:
        print(f"[Email Poller] Connection error: {e}")


def main():
    print(f"[Email Poller] Starting. Polling every {POLL_INTERVAL}s...")
    print(f"[Email Poller] Submitting to: {BACKEND_URL}\n")

    while True:
        try:
            poll_inbox()
        except Exception as e:
            print(f"[Error] {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()