# Complaint Intake Channels — Prototype vs Production

> Union Bank AI Complaint Dashboard  
> Covers: Twitter/X Channel & IVR Channel

---

## Channel 2 — Twitter/X

### What We Have Now (Prototype)

A local Python script (`twitter_simulator.py`) with a menu-driven interface that sends pre-written fake tweet payloads directly to the FastAPI backend.

**How it works:**
```
Developer runs script → picks a sample tweet from menu
→ script POSTs to /api/v1/complaints/submit
→ saved in Supabase with channel = "twitter"
```

**What it can do:**
- 5 pre-loaded realistic complaint tweets
- Custom tweet input option
- Bulk send all tweets at once (demo mode)
- Correctly sets `channel = "twitter"` and `customer_id = @handle`

**What it cannot do:**
- Cannot read real tweets from Twitter/X
- No real-time monitoring
- No actual Twitter API connection
- No image/media attachment from tweets
- No retweet or thread context

---

### What Production Needs

#### Step 1 — Twitter Developer Account
- Apply at `developer.twitter.com`
- Takes 1–3 days for approval
- Requires a clear use case description (mention "banking complaint monitoring")

#### Step 2 — API Tier Decision

| Tier | Cost | What You Get | Good For |
|------|------|-------------|----------|
| Free | $0/month | 500 tweets/month read, no streaming | Testing only |
| Basic | $100/month | 10,000 tweets/month, limited stream | Small bank pilot |
| Pro | $5,000/month | 1M tweets/month, full filtered stream | Production use |
| Enterprise | Custom | Unlimited, full firehose | Full bank deployment |


#### Step 3 — Code Changes Needed

Replace `twitter_simulator.py` with a real poller using Twitter API v2:

```python
# Production approach — Filtered Stream API
# Monitors tweets mentioning @UnionBankOfIndia in real time

import tweepy

client = tweepy.StreamingClient(bearer_token=TWITTER_BEARER_TOKEN)

# Add rules — what tweets to capture
client.add_rules(tweepy.StreamRule("@UnionBankOfIndia"))
client.add_rules(tweepy.StreamRule("#UnionBankComplaint"))
client.add_rules(tweepy.StreamRule("@UnionBankOfIndia complaint OR problem OR failed OR issue"))
```

**Changes required in existing code:**

| What | Change |
|------|--------|
| `twitter_simulator.py` | Replace with `twitter_stream_listener.py` using Tweepy |
| `.env` | Add `TWITTER_BEARER_TOKEN`, `TWITTER_API_KEY`, `TWITTER_API_SECRET` |
| `customer_id` | Use real Twitter user ID instead of `@handle` |
| `complaint_text` | Include tweet media, thread context, retweet count |
| Backend route | No change needed — same `/api/v1/complaints/submit` |
| DB schema | Add `tweet_id`, `retweet_count`, `like_count` to metadata |

#### Step 4 — Additional Production Requirements

- **Rate limit handling** — Twitter enforces strict rate limits; need exponential backoff
- **Duplicate detection** — same user can tweet same complaint multiple times; deduplicate by `tweet_id`
- **Sentiment pre-filter** — filter out non-complaint tweets (positive mentions, news) before submitting
- **Language filter** — handle Hindi, regional language tweets using `lang` parameter
- **Webhook vs polling** — production should use Account Activity API webhook, not polling

---

### Effort to Go Production

| Task | Time |
|------|------|
| Twitter developer account approval | 1–3 days (waiting) |
| Tweepy integration + stream listener | 1 day |
| Rate limit + retry handling | 0.5 day |
| Duplicate tweet detection | 0.5 day |
| Language + sentiment pre-filter | 1 day |
| Testing and deployment | 1 day |
| **Total** | **~5 days + approval wait** |

---

## Channel 3 — IVR (Voice Call)

### What We Have Now (Prototype)

A local Python script (`ivr_simulator.py`) that generates realistic complaint audio files using OpenAI TTS, transcribes them with OpenAI Whisper, and submits the transcript to the FastAPI backend.

**How it works:**
```
Developer picks a call from menu
→ OpenAI TTS generates MP3 audio (saved to sample_calls/)
→ OpenAI Whisper transcribes MP3 to text
→ script POSTs transcript to /api/v1/complaints/submit
→ saved in Supabase with channel = "ivr"
```

**What it can do:**
- 5 pre-loaded realistic IVR complaint scenarios
- Generates natural-sounding audio (5 different voices)
- Whisper transcription with high accuracy
- Correctly sets `channel = "ivr"` and `customer_id`
- Audio files reused after first generation (no duplicate API calls)

**What it cannot do:**
- Cannot handle real incoming phone calls
- No actual telephony/PSTN connection
- No real-time call streaming
- No DTMF (press 1 for X, press 2 for Y) handling
- No call recording from real customer calls
- No caller ID / phone number lookup against CRM

---

### What Production Needs

#### Step 1 — Telephony Provider Decision

| Provider | Cost | Best For |
|----------|------|----------|
| Twilio | $1/month per number + $0.013/min | Most popular, easy setup |
| AWS Connect | Pay per minute (~$0.018/min) | Already on AWS |
| Exotel | ₹2,000/month + usage | India-specific, cheaper |
| Tata Tele | Custom enterprise pricing | PSB banks in India |


#### Step 2 — Architecture Change

Production IVR flow is very different from prototype:

```
Customer calls Union Bank number
        ↓
Telephony provider (Exotel/Twilio) receives call
        ↓
Provider streams audio to your server via webhook
        ↓
Your server sends audio chunks to Whisper in real time
        ↓
Transcript built as customer speaks
        ↓
On call end → POST to /api/v1/complaints/submit
        ↓
Saved in Supabase with channel = "ivr"
```

#### Step 3 — Code Changes Needed

**New files required:**

```
backend/
└── app/
    └── channels/
        └── ivr/
            ├── call_webhook.py        # receives incoming call from Exotel/Twilio
            ├── stream_transcriber.py  # real-time Whisper streaming
            └── caller_lookup.py       # match phone number to CRM customer ID
```

**New webhook route needed in FastAPI:**

```python
# New route — receives call from Exotel webhook
@router.post("/api/v1/channels/ivr/incoming")
async def handle_incoming_call(
    caller_number: str = Form(...),
    call_recording_url: str = Form(...),   # Exotel sends recording URL
    call_duration: int = Form(...),
    call_id: str = Form(...),
):
    # Download recording → transcribe → submit complaint
    ...
```

**Changes required in existing code:**

| What | Change |
|------|--------|
| `ivr_simulator.py` | Keep for demo only — not used in production |
| Backend | Add new `/api/v1/channels/ivr/incoming` webhook route |
| `.env` | Add `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_SID` |
| `customer_id` | Lookup caller phone number in bank CRM |
| `complaint_text` | Include call duration, call ID, caller number |
| DB schema | Add `call_id`, `call_duration`, `caller_number`, `call_recording_url` |
| Whisper | Switch from file-based to real-time streaming transcription |

#### Step 4 — Additional Production Requirements

- **Call recording storage** — recordings must be stored securely (RBI data localisation rules apply)
- **PII in audio** — caller may say account number, Aadhaar — need audio-level PII masking
- **Hindi/regional language support** — Whisper supports Hindi but accuracy varies; may need IndicWhisper
- **Real-time vs post-call** — real-time transcription is harder; post-call (after hang-up) is simpler and more accurate
- **Call queue integration** — if call center already uses Genesys or Avaya, integrate at that layer
- **Minimum call duration filter** — ignore calls under 10 seconds (wrong number, hang-ups)

---

### Effort to Go Production

| Task | Time |
|------|------|
| Exotel/Twilio account setup + phone number | 1 day |
| Webhook endpoint in FastAPI | 1 day |
| Real-time audio streaming to Whisper | 2 days |
| Caller ID → CRM customer lookup | 1 day |
| Audio PII masking | 1 day |
| Hindi/regional language handling | 1–2 days |
| Call recording secure storage | 1 day |
| Testing with real calls | 2 days |
| **Total** | **~10–11 days** |

---

## Summary Table

| | Twitter/X | IVR |
|---|---|---|
| **Prototype status** | ✅ Working simulator | ✅ Working simulator |
| **Production cost** | $5,000/month (Pro API) | ~₹2,000/month + usage (Exotel) |
| **Code changes** | Medium — swap simulator for Tweepy stream | Large — new webhook architecture |
| **New accounts needed** | Twitter Developer (1–3 day approval) | Exotel/Twilio (same day) |
| **Effort to production** | ~5 days | ~10–11 days |
| **Biggest risk** | Twitter API approval + cost | Real-time audio streaming complexity |
| **Backend route changes** | None — same endpoint | New webhook route needed |
| **DB schema changes** | Add tweet metadata fields | Add call metadata fields |

---

## What Does NOT Change in Production

For both channels, the following remain exactly the same:

- `POST /api/v1/complaints/submit` endpoint — no changes
- Supabase DB schema for core complaint fields
- LangGraph AI pipeline — runs identically regardless of channel
- Dashboard UI — already reads `channel` field to display icons
- Auth middleware (`X-API-Key` header)
- Idempotency handling

The channels are just **intake pipes** — everything after submission is already production-ready.