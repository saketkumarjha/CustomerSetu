import uuid
import requests
from dotenv import load_dotenv
import os

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL")
API_KEY = os.getenv("API_KEY")

# Preloaded realistic complaint tweets for demo
SAMPLE_TWEETS = [
    {
        "username": "@rahul_sharma92",
        "text": "@UnionBankOfIndia my UPI payment of ₹15,000 failed but amount got deducted from my account. Transaction ID: UPI2026050812345. Please help urgently!"
    },
    {
        "username": "@priya_mumbai",
        "text": "@UnionBankOfIndia ATM at Andheri branch swallowed my card and didn't dispense cash. I've been waiting 3 days for resolution. This is completely unacceptable!"
    },
    {
        "username": "@amit_delhi_ncr",
        "text": "@UnionBankOfIndia my home loan EMI was debited twice this month. Account number ending 4521. Nobody at customer care is responding. #BankingFail"
    },
    {
        "username": "@sneha_bangalore",
        "text": "@UnionBankOfIndia internet banking is down since yesterday. I can't pay my credit card bill and the due date is today. Will you waive the late fee?"
    },
    {
        "username": "@vikram_trades",
        "text": "@UnionBankOfIndia FD maturity amount not credited to my account even after 5 days of maturity date. Branch is not giving any clear answer. #UnionBank"
    },
]


def submit_tweet_as_complaint(username: str, tweet_text: str):
    """Submit a tweet as a complaint to the backend."""
    headers = {
        "X-API-Key": API_KEY,
        "X-Idempotency-Key": str(uuid.uuid4()),
    }

    # Build complaint text with Twitter context
    complaint_text = f"[Twitter complaint from {username}]\n\n{tweet_text}"

    payload = {
        "complaint_text": complaint_text,
        "channel": "twitter",
        "customer_id": username,
    }

    try:
        resp = requests.post(BACKEND_URL, data=payload, headers=headers, timeout=10)

        if resp.status_code == 201:
            data = resp.json()
            print(f"    [✓] Saved as {data['complaint_id']}")
            print(f"    Pipeline: POST /api/v1/pipeline/run/{data['complaint_id']}")
        else:
            print(f"    [✗] Failed ({resp.status_code}): {resp.text}")

    except requests.exceptions.ConnectionError:
        print("    [✗] Cannot reach FastAPI — is it running on port 8000?")
    except Exception as e:
        print(f"    [✗] Error: {e}")


def show_menu():
    print("\n" + "="*55)
    print("   Twitter/X Complaint Simulator — Union Bank")
    print("="*55)
    print("\nChoose an option:")
    print("  [1-5] Send a preloaded sample tweet")
    print("  [6]   Type your own custom tweet")
    print("  [7]   Send ALL sample tweets at once (bulk demo)")
    print("  [0]   Exit")
    print()


def main():
    print("\n[Twitter Simulator] Starting...")
    print(f"[Twitter Simulator] Submitting to: {BACKEND_URL}")

    while True:
        show_menu()

        # Show sample tweets
        for i, tweet in enumerate(SAMPLE_TWEETS, 1):
            print(f"  {i}. {tweet['username']}: {tweet['text'][:60]}...")

        print()
        choice = input("Enter choice: ").strip()

        if choice == "0":
            print("Exiting.")
            break

        elif choice in ["1", "2", "3", "4", "5"]:
            tweet = SAMPLE_TWEETS[int(choice) - 1]
            print(f"\n[→] Sending tweet from {tweet['username']}...")
            print(f"    Text: {tweet['text']}")
            submit_tweet_as_complaint(tweet["username"], tweet["text"])

        elif choice == "6":
            print("\nEnter tweet details:")
            username = input("  Twitter handle (e.g. @your_name): ").strip()
            if not username.startswith("@"):
                username = "@" + username
            text = input("  Tweet text: ").strip()
            if not text:
                print("  [!] Tweet text cannot be empty.")
                continue
            print(f"\n[→] Sending custom tweet from {username}...")
            submit_tweet_as_complaint(username, text)

        elif choice == "7":
            print(f"\n[→] Sending all {len(SAMPLE_TWEETS)} sample tweets...")
            for tweet in SAMPLE_TWEETS:
                print(f"\n[→] {tweet['username']}")
                submit_tweet_as_complaint(tweet["username"], tweet["text"])
            print("\n[✓] All tweets sent.")

        else:
            print("  [!] Invalid choice. Try again.")


if __name__ == "__main__":
    main()