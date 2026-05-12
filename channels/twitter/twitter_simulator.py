"""
Twitter/X Complaint Simulator — Union Bank of India

Submits sample or custom tweets as complaints to the FastAPI backend,
then immediately triggers the AI pipeline for each one.

Usage:
    cd channels/twitter
    python twitter_simulator.py
"""

import os
import uuid
import time

import requests
from dotenv import load_dotenv

# Load .env from the same directory as this script (not cwd)
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

_BASE = (os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY") or "sk_my_super_secret_key_123"

SUBMIT_URL  = f"{_BASE}/api/v1/complaints/submit"
PIPELINE_URL = f"{_BASE}/api/v1/pipeline/run"   # + /{complaint_id}

# ── Sample tweets ─────────────────────────────────────────────────────────────

SAMPLE_TWEETS = [
    {
        "username": "@rahul_sharma92",
        "text": (
            "@UnionBankOfIndia my UPI payment of ₹15,000 failed but amount got "
            "deducted from my account. Transaction ID: UPI2026050812345. Please help urgently!"
        ),
    },
    {
        "username": "@priya_mumbai",
        "text": (
            "@UnionBankOfIndia ATM at Andheri branch swallowed my card and didn't "
            "dispense cash. I've been waiting 3 days for resolution. This is completely unacceptable!"
        ),
    },
    {
        "username": "@amit_delhi_ncr",
        "text": (
            "@UnionBankOfIndia my home loan EMI was debited twice this month. "
            "Account number ending 4521. Nobody at customer care is responding. #BankingFail"
        ),
    },
    {
        "username": "@sneha_bangalore",
        "text": (
            "@UnionBankOfIndia internet banking is down since yesterday. I can't pay "
            "my credit card bill and the due date is today. Will you waive the late fee?"
        ),
    },
    {
        "username": "@vikram_trades",
        "text": (
            "@UnionBankOfIndia FD maturity amount not credited to my account even after "
            "5 days of maturity date. Branch is not giving any clear answer. #UnionBank"
        ),
    },
]


# ── Core helpers ──────────────────────────────────────────────────────────────

def _auth_headers(idempotency_key: str) -> dict:
    return {
        "X-API-Key": API_KEY,
        "X-Idempotency-Key": idempotency_key,
    }


def submit_tweet_as_complaint(username: str, tweet_text: str) -> str | None:
    """
    Submit a tweet as a complaint.
    Returns the complaint_id on success, None on failure.
    """
    idempotency_key = str(uuid.uuid4())
    complaint_text = f"[Twitter complaint from {username}]\n\n{tweet_text}"

    # The endpoint uses Form fields — send as multipart/form-data via data=
    payload = {
        "complaint_text": complaint_text,
        "channel": "twitter",
        "customer_id": username,
    }

    try:
        resp = requests.post(
            SUBMIT_URL,
            data=payload,
            headers=_auth_headers(idempotency_key),
            timeout=15,
        )
    except requests.exceptions.ConnectionError:
        print(f"    [✗] Cannot reach backend at {_BASE} — is it running?")
        return None
    except Exception as exc:
        print(f"    [✗] Request error: {exc}")
        return None

    if resp.status_code == 201:
        data = resp.json()
        complaint_id = data.get("complaint_id", "?")
        print(f"    [✓] Registered as {complaint_id}")
        return complaint_id
    else:
        print(f"    [✗] Submit failed ({resp.status_code}): {resp.text[:200]}")
        return None


def trigger_pipeline(complaint_id: str) -> None:
    """Kick off the AI pipeline for a complaint."""
    url = f"{PIPELINE_URL}/{complaint_id}"
    try:
        resp = requests.post(url, headers={"X-API-Key": API_KEY}, timeout=10)
        if resp.status_code in (200, 202):
            data = resp.json()
            stream = data.get("stream_url", "")
            print(f"    [✓] Pipeline started — stream: {_BASE}{stream}")
        else:
            print(f"    [!] Pipeline trigger failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as exc:
        print(f"    [!] Pipeline trigger error: {exc}")


def submit_and_run(username: str, tweet_text: str) -> None:
    """Submit a tweet complaint and immediately trigger the AI pipeline."""
    complaint_id = submit_tweet_as_complaint(username, tweet_text)
    if complaint_id:
        trigger_pipeline(complaint_id)


# ── CLI ───────────────────────────────────────────────────────────────────────

def show_menu() -> None:
    print("\n" + "=" * 55)
    print("   Twitter/X Complaint Simulator — Union Bank")
    print("=" * 55)
    print(f"   Backend : {_BASE}")
    print(f"   API Key : {API_KEY[:12]}…")
    print("=" * 55)
    print("\nChoose an option:")
    print("  [1-5] Send a preloaded sample tweet")
    print("  [6]   Type your own custom tweet")
    print("  [7]   Send ALL sample tweets at once (bulk demo)")
    print("  [0]   Exit")
    print()


def main() -> None:
    print("\n[Twitter Simulator] Starting…")

    while True:
        show_menu()

        for i, tweet in enumerate(SAMPLE_TWEETS, 1):
            preview = tweet["text"][:65].replace("\n", " ")
            print(f"  {i}. {tweet['username']}: {preview}…")

        print()
        choice = input("Enter choice: ").strip()

        if choice == "0":
            print("Exiting.")
            break

        elif choice in ("1", "2", "3", "4", "5"):
            tweet = SAMPLE_TWEETS[int(choice) - 1]
            print(f"\n[→] Sending tweet from {tweet['username']}…")
            print(f"    Text: {tweet['text'][:80]}")
            submit_and_run(tweet["username"], tweet["text"])

        elif choice == "6":
            print("\nEnter tweet details:")
            username = input("  Twitter handle (e.g. @your_name): ").strip()
            if not username:
                print("  [!] Handle cannot be empty.")
                continue
            if not username.startswith("@"):
                username = "@" + username
            text = input("  Tweet text: ").strip()
            if not text:
                print("  [!] Tweet text cannot be empty.")
                continue
            print(f"\n[→] Sending custom tweet from {username}…")
            submit_and_run(username, text)

        elif choice == "7":
            print(f"\n[→] Sending all {len(SAMPLE_TWEETS)} sample tweets…")
            for tweet in SAMPLE_TWEETS:
                print(f"\n[→] {tweet['username']}")
                submit_and_run(tweet["username"], tweet["text"])
                time.sleep(0.5)   # small delay to avoid rate-limit (10/min)
            print("\n[✓] All tweets sent and pipelines triggered.")

        else:
            print("  [!] Invalid choice. Try again.")


if __name__ == "__main__":
    main()
