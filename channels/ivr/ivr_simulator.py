import uuid
import os
import requests
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

_script_dir = Path(__file__).resolve().parent
# Load next to this script, then sample_calls/.env (keys not already in the environment)
load_dotenv(_script_dir / ".env")
load_dotenv(_script_dir / "sample_calls" / ".env")

BACKEND_URL = os.getenv("BACKEND_URL")
API_KEY = os.getenv("API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise SystemExit(
        "OPENAI_API_KEY is not set.\n"
        f"Add it to {_script_dir / '.env'} or {_script_dir / 'sample_calls' / '.env'}, "
        "or run: export OPENAI_API_KEY='your-key'"
    )

client = OpenAI(api_key=OPENAI_API_KEY)

SAMPLE_CALLS = [
    {
        "id": 1,
        "caller": "Rajesh Kumar",
        "customer_id": "CUST-RK-9821",
        "phone": "+91-98210-XXXXX",
        "voice": "onyx",
        "script": (
            "Hello, I am calling to complain about a UPI transaction failure. "
            "Yesterday I tried to transfer fifteen thousand rupees to my friend "
            "using Union Bank mobile app. The amount got deducted from my account "
            "but the recipient never received the money. The transaction ID is "
            "UPI two zero two six zero five zero eight one two three four five. "
            "I have been trying to reach customer care since morning but no one "
            "is picking up. Please resolve this urgently as I need that money back."
        ),
    },
    {
        "id": 2,
        "caller": "Priya Mehta",
        "customer_id": "CUST-PM-4453",
        "phone": "+91-91234-XXXXX",
        "voice": "nova",
        "script": (
            "Hi, I want to register a complaint regarding my credit card. "
            "I received my credit card statement this month and there are two "
            "transactions that I did not make. One is for eight thousand rupees "
            "at an online shopping site and another for three thousand five hundred "
            "at a restaurant in Delhi. I have never been to Delhi and I did not "
            "make any online purchase on those dates. I think my card details "
            "have been stolen. Please block my card immediately and initiate "
            "a fraud investigation. This is very urgent."
        ),
    },
    {
        "id": 3,
        "caller": "Amit Singh",
        "customer_id": "CUST-AS-7732",
        "phone": "+91-87654-XXXXX",
        "voice": "echo",
        "script": (
            "Good morning. I am calling about my home loan account. "
            "My EMI of thirty two thousand rupees was supposed to be debited "
            "on the fifth of this month but it got debited twice. "
            "Once on the fifth and again on the seventh. "
            "My account number is ending with four five two one. "
            "Due to this double deduction my account went into negative balance "
            "and I got charged an overdraft fee as well. "
            "I want the extra EMI amount refunded immediately along with "
            "the overdraft charges. Please treat this as high priority."
        ),
    },
    {
        "id": 4,
        "caller": "Sunita Rao",
        "customer_id": "CUST-SR-2281",
        "phone": "+91-99887-XXXXX",
        "voice": "shimmer",
        "script": (
            "Hello, I am very frustrated right now. I went to the ATM "
            "at the Koramangala branch in Bangalore this morning to withdraw "
            "ten thousand rupees. The ATM showed transaction successful "
            "and debited the amount from my account but no cash came out. "
            "I waited for five minutes but nothing happened. "
            "I have the transaction receipt with me. The reference number is "
            "ATM two zero two six zero five zero eight nine nine nine. "
            "I need the money credited back to my account today. "
            "Please help me as soon as possible."
        ),
    },
    {
        "id": 5,
        "caller": "Mohammed Farouk",
        "customer_id": "CUST-MF-6610",
        "phone": "+91-70000-XXXXX",
        "voice": "alloy",
        "script": (
            "I am calling to complain about my fixed deposit. "
            "My FD of five lakh rupees matured on the first of this month. "
            "As per the instructions I gave at the branch, the maturity amount "
            "should have been credited to my savings account automatically. "
            "But it has been seven days and I still have not received the amount. "
            "I visited the branch twice and they keep saying it will be done tomorrow. "
            "I am an senior citizen and I depend on this FD interest for my monthly "
            "expenses. This delay is causing me a lot of hardship. "
            "Please escalate this matter to a senior manager immediately."
        ),
    },
]


def generate_audio(call: dict) -> str:
    """Generate MP3 audio from complaint script using OpenAI TTS."""
    filename = f"sample_calls/call_{call['id']}_{call['caller'].replace(' ', '_')}.mp3"

    if os.path.exists(filename):
        print(f"    [~] Audio already exists: {filename}")
        return filename

    print(f"    [→] Generating audio for {call['caller']}...")
    response = client.audio.speech.create(
        model="tts-1",
        voice=call["voice"],
        input=call["script"],
    )

    response.stream_to_file(filename)
    print(f"    [✓] Audio saved: {filename}")
    return filename


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file using OpenAI Whisper."""
    print(f"    [→] Transcribing with Whisper...")
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="en",
        )
    print(f"    [✓] Transcription complete.")
    return transcript.text


def submit_complaint(transcript: str, customer_id: str, caller: str):
    """POST transcribed complaint to FastAPI backend."""
    headers = {
        "X-API-Key": API_KEY,
        "X-Idempotency-Key": str(uuid.uuid4()),
    }

    complaint_text = (
        f"[IVR Call from {caller} | Customer ID: {customer_id}]\n\n"
        f"{transcript}"
    )

    payload = {
        "complaint_text": complaint_text,
        "channel": "ivr",
        "customer_id": customer_id,
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


def run_full_pipeline(call: dict):
    """Generate audio → transcribe → submit for one call."""
    print(f"\n{'='*55}")
    print(f"  Processing call from: {call['caller']}")
    print(f"  Customer ID: {call['customer_id']}")
    print(f"{'='*55}")

    audio_path = generate_audio(call)
    transcript = transcribe_audio(audio_path)

    print(f"\n  Transcript preview:")
    print(f"  \"{transcript[:120]}...\"")

    submit_complaint(transcript, call["customer_id"], call["caller"])


def show_menu():
    print("\n" + "="*55)
    print("   IVR Call Simulator — Union Bank")
    print("="*55)
    print("\nSample calls available:")
    for call in SAMPLE_CALLS:
        print(f"  [{call['id']}] {call['caller']} — {call['script'][:50]}...")
    print(f"\n  [6] Generate ALL audio files (one-time setup)")
    print(f"  [7] Run ALL calls through full pipeline")
    print(f"  [0] Exit\n")


def main():
    print("\n[IVR Simulator] Starting...")
    print(f"[IVR Simulator] Submitting to: {BACKEND_URL}")

    while True:
        show_menu()
        choice = input("Enter choice: ").strip()

        if choice == "0":
            print("Exiting.")
            break

        elif choice in ["1", "2", "3", "4", "5"]:
            call = SAMPLE_CALLS[int(choice) - 1]
            run_full_pipeline(call)

        elif choice == "6":
            print("\n[→] Generating all audio files...")
            for call in SAMPLE_CALLS:
                generate_audio(call)
            print("\n[✓] All audio files ready in sample_calls/")

        elif choice == "7":
            print(f"\n[→] Running all {len(SAMPLE_CALLS)} calls through pipeline...")
            for call in SAMPLE_CALLS:
                run_full_pipeline(call)
            print("\n[✓] All calls processed.")

        else:
            print("  [!] Invalid choice.")


if __name__ == "__main__":
    main()