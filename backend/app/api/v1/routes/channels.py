"""
Channel Demo Routes — Hackathon prototype endpoints for Twitter and IVR channels.

In production these channels use real external services (Twitter Streaming API,
Exotel/Twilio IVR). For the prototype demo these endpoints simulate the exact
same intake pipeline so judges can trigger complaints from the UI.

Routes:
  POST /api/v1/channels/twitter/demo        — Submit a sample tweet as complaint
  POST /api/v1/channels/ivr/demo            — Submit a sample IVR call as complaint
  GET  /api/v1/channels/ivr/audio/{filename} — Serve pre-generated MP3 audio files
"""
import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.db.supabase_client import get_supabase

async def _trigger_pipeline_bg(complaint_id: str) -> None:
    """Fire-and-forget: start the AI pipeline for a complaint in the background."""
    try:
        from app.services.supervisor.graph import pipeline_graph
        from app.services.supervisor.pipeline_state import PipelineState
        from app.services.supervisor.audit_trail import update_complaint_status
        from app.services.supervisor.event_bus import event_bus
        from app.api.v1.routes.pipeline import _save_pipeline_outputs

        supabase = get_supabase()
        result = supabase.table("complaints").select("*").eq("complaint_id", complaint_id).execute()
        if not result.data:
            return
        complaint = result.data[0]

        # Reset tier/escalation fields BEFORE setting pipeline_status=processing
        # so the DB trigger (trigger_add_to_agent_queue) cannot fire with stale
        # defaults and create a premature Tier-4 queue entry.
        supabase.table("complaints").update({
            "current_tier": 0,
            "assigned_tier": 1,
            "is_escalating": False,
            "escalation_count": 0,
            "escalation_path": [],
            "max_tier_reached": 0,
            "total_escalations_count": 0,
            "tier_pending_at": None,
            "assigned_agent_id": None,
        }).eq("complaint_id", complaint_id).execute()

        event_bus.create_queue(complaint_id)
        await update_complaint_status(complaint_id, "processing")

        initial_state: PipelineState = {
            "complaint_id": complaint_id,
            "customer_id": complaint.get("customer_id", ""),
            "channel": complaint.get("channel", ""),
            "complaint_text": complaint.get("original_text") or "",
            "merged_text": complaint.get("merged_text") or complaint.get("original_text") or "",
            "image_url": None,
            "idempotency_key": None,
            "masked_text": None, "language": None, "pii_entities_found": None,
            "is_duplicate": None, "duplicate_of": None, "duplicate_similarity": None,
            "category": None, "category_confidence": None, "sentiment": None,
            "urgency_score": None, "escalation_flag": None, "compliance_category": None,
            "is_rbi_reportable": None, "rbi_supervisor_override": None,
            "severity": None, "severity_score": None, "severity_breakdown": None,
            "context_documents": None, "draft_response": None, "root_cause": None,
            "action_steps": None, "confidence_score": None, "authority_sufficient": None,
            "grounding_score": None, "grounding_warnings": None, "route": None,
            "risk_score": None, "sla_hours": None, "rbi_tat_deadline": None,
            "routing_reason": None, "current_tier": 0, "assigned_tier": None,
            "escalation_decision": None, "explanation_trace": [], "errors": [],
            "pipeline_status": "started", "current_agent": None,
            "formatted_response": None, "notification_channel": None,
            "customer_notified_at": None, "escalation_info": None,
            "escalation_count": 0, "escalation_path": [], "is_escalating": False,
            "escalation_orchestrator_result": None,
            "tier_level": 0, "tier_scope": None, "tier_contact_info": None,
            "previous_tier_attempts": None, "tier_kb_coverage_score": None,
            "missing_info_indicators": None, "resolution_type": None,
        }

        final_state = await pipeline_graph.ainvoke(initial_state)
        await _save_pipeline_outputs(complaint_id, final_state)
        await event_bus.publish(complaint_id, {
            "event": "pipeline_complete",
            "complaint_id": complaint_id,
            "route": final_state.get("route"),
            "category": final_state.get("category"),
        })
    except Exception as exc:
        print(f"[CHANNELS] Pipeline bg task failed for {complaint_id}: {exc}")
    finally:
        try:
            from app.services.supervisor.event_bus import event_bus
            await event_bus.close(complaint_id)
        except Exception:
            pass

router = APIRouter()

# Path to pre-generated IVR sample MP3 files (generated once by ivr_simulator.py)
SAMPLE_CALLS_DIR = Path(__file__).resolve().parents[5] / "channels" / "ivr" / "sample_calls"

# ── Sample data (mirrors the simulator scripts) ────────────────────────────────

SAMPLE_TWEETS = [
    {
        "index": 0,
        "username": "@rahul_sharma92",
        "text": (
            "@UnionBankOfIndia my UPI payment of ₹15,000 failed but amount got deducted "
            "from my account. Transaction ID: UPI2026050812345. Please help urgently!"
        ),
    },
    {
        "index": 1,
        "username": "@priya_mumbai",
        "text": (
            "@UnionBankOfIndia ATM at Andheri branch swallowed my card and didn't dispense "
            "cash. I've been waiting 3 days for resolution. This is completely unacceptable!"
        ),
    },
    {
        "index": 2,
        "username": "@amit_delhi_ncr",
        "text": (
            "@UnionBankOfIndia my home loan EMI was debited twice this month. Account number "
            "ending 4521. Nobody at customer care is responding. #BankingFail"
        ),
    },
    {
        "index": 3,
        "username": "@sneha_bangalore",
        "text": (
            "@UnionBankOfIndia internet banking is down since yesterday. I can't pay my "
            "credit card bill and the due date is today. Will you waive the late fee?"
        ),
    },
    {
        "index": 4,
        "username": "@vikram_trades",
        "text": (
            "@UnionBankOfIndia FD maturity amount not credited to my account even after "
            "5 days of maturity date. Branch is not giving any clear answer. #UnionBank"
        ),
    },
]

SAMPLE_CALLS = [
    {
        "index": 0,
        "caller": "Rajesh Kumar",
        "customer_id": "CUST-RK-9821",
        "audio_file": "call_1_Rajesh_Kumar.mp3",
        "transcript": (
            "Hello, I am calling to complain about a UPI transaction failure. "
            "Yesterday I tried to transfer fifteen thousand rupees to my friend "
            "using Union Bank mobile app. The amount got deducted from my account "
            "but the recipient never received the money. The transaction ID is "
            "UPI202605081234 5. I have been trying to reach customer care since "
            "morning but no one is picking up. Please resolve this urgently as I "
            "need that money back."
        ),
    },
    {
        "index": 1,
        "caller": "Priya Mehta",
        "customer_id": "CUST-PM-4453",
        "audio_file": "call_2_Priya_Mehta.mp3",
        "transcript": (
            "Hi, I want to register a complaint regarding my credit card. "
            "I received my credit card statement this month and there are two "
            "transactions that I did not make. One is for eight thousand rupees "
            "at an online shopping site and another for three thousand five hundred "
            "at a restaurant in Delhi. I think my card details have been stolen. "
            "Please block my card immediately and initiate a fraud investigation."
        ),
    },
    {
        "index": 2,
        "caller": "Amit Singh",
        "customer_id": "CUST-AS-7732",
        "audio_file": "call_3_Amit_Singh.mp3",
        "transcript": (
            "Good morning. I am calling about my home loan account. "
            "My EMI of thirty two thousand rupees was supposed to be debited "
            "on the fifth of this month but it got debited twice. "
            "Due to this double deduction my account went into negative balance "
            "and I got charged an overdraft fee as well. "
            "I want the extra EMI amount refunded immediately along with "
            "the overdraft charges."
        ),
    },
    {
        "index": 3,
        "caller": "Sunita Rao",
        "customer_id": "CUST-SR-2281",
        "audio_file": "call_4_Sunita_Rao.mp3",
        "transcript": (
            "Hello, I am very frustrated right now. I went to the ATM "
            "at the Koramangala branch in Bangalore this morning to withdraw "
            "ten thousand rupees. The ATM showed transaction successful "
            "and debited the amount from my account but no cash came out. "
            "I have the transaction receipt with me. "
            "I need the money credited back to my account today."
        ),
    },
    {
        "index": 4,
        "caller": "Mohammed Farouk",
        "customer_id": "CUST-MF-6610",
        "audio_file": "call_5_Mohammed_Farouk.mp3",
        "transcript": (
            "I am calling to complain about my fixed deposit. "
            "My FD of five lakh rupees matured on the first of this month. "
            "As per the instructions I gave at the branch, the maturity amount "
            "should have been credited to my savings account automatically. "
            "But it has been seven days and I still have not received the amount. "
            "I am a senior citizen and I depend on this FD interest for my monthly "
            "expenses. Please escalate this matter to a senior manager immediately."
        ),
    },
]


# ── Request / Response models ──────────────────────────────────────────────────

class TwitterDemoRequest(BaseModel):
    tweet_index: int
    auto_run: bool = True


class IVRDemoRequest(BaseModel):
    call_index: int
    auto_run: bool = True


class ChannelDemoResponse(BaseModel):
    complaint_id: str
    channel: str
    customer_id: str
    preview: str
    message: str


# ── Helper ─────────────────────────────────────────────────────────────────────

def _insert_complaint(channel: str, customer_id: str, complaint_text: str) -> str:
    """Insert a complaint record directly into Supabase and return complaint_id."""
    supabase = get_supabase()
    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"

    record = {
        "complaint_id": complaint_id,
        "customer_id": customer_id,
        "channel": channel,
        "original_text": complaint_text,
        "merged_text": complaint_text,
        "pipeline_status": "pending",
        "status": "pending",
        "initial_tier": 0,
        "current_tier": 0,
        "max_tier_reached": 0,
        "missing_info_indicators": [],
        "context_documents": [],
        "escalation_path": [],
    }

    try:
        supabase.table("complaints").insert(record).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save complaint: {str(exc)}",
        )

    return complaint_id


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/twitter/demo",
    response_model=ChannelDemoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a tweet complaint (prototype demo)",
)
async def twitter_demo(req: TwitterDemoRequest, background_tasks: BackgroundTasks):
    """
    Prototype demo endpoint — simulates a tweet being picked up by the
    Twitter poller and submitted to the complaint pipeline.

    In production this is replaced by a Tweepy Filtered Stream listener
    monitoring @UnionBankOfIndia mentions in real time.
    """
    if not 0 <= req.tweet_index <= 4:
        raise HTTPException(status_code=400, detail="tweet_index must be 0–4")

    tweet = SAMPLE_TWEETS[req.tweet_index]
    complaint_text = f"[Twitter complaint from {tweet['username']}]\n\n{tweet['text']}"

    complaint_id = _insert_complaint(
        channel="twitter",
        customer_id=tweet["username"],
        complaint_text=complaint_text,
    )

    if req.auto_run:
        background_tasks.add_task(_trigger_pipeline_bg, complaint_id)

    return ChannelDemoResponse(
        complaint_id=complaint_id,
        channel="twitter",
        customer_id=tweet["username"],
        preview=tweet["text"][:100],
        message=(
            f"Tweet submitted as {complaint_id}. AI pipeline started."
            if req.auto_run
            else f"Tweet submitted as {complaint_id}. Run pipeline manually."
        ),
    )


@router.post(
    "/ivr/demo",
    response_model=ChannelDemoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate an IVR call complaint (prototype demo)",
)
async def ivr_demo(req: IVRDemoRequest, background_tasks: BackgroundTasks):
    """
    Prototype demo endpoint — simulates an IVR call being transcribed by
    Whisper and submitted to the complaint pipeline.
    """
    if not 0 <= req.call_index <= 4:
        raise HTTPException(status_code=400, detail="call_index must be 0–4")

    call = SAMPLE_CALLS[req.call_index]
    complaint_text = (
        f"[IVR Call from {call['caller']} | Customer ID: {call['customer_id']}]\n\n"
        f"{call['transcript']}"
    )

    complaint_id = _insert_complaint(
        channel="ivr",
        customer_id=call["customer_id"],
        complaint_text=complaint_text,
    )

    if req.auto_run:
        background_tasks.add_task(_trigger_pipeline_bg, complaint_id)

    return ChannelDemoResponse(
        complaint_id=complaint_id,
        channel="ivr",
        customer_id=call["customer_id"],
        preview=call["transcript"][:100],
        message=(
            f"IVR call submitted as {complaint_id}. AI pipeline started."
            if req.auto_run
            else f"IVR call submitted as {complaint_id}. Run pipeline manually."
        ),
    )


@router.get(
    "/ivr/audio/{filename}",
    summary="Serve pre-generated IVR sample audio files",
)
async def get_ivr_audio(filename: str):
    """
    Serve pre-generated MP3 audio files for IVR demo playback.
    Files are generated once by ivr_simulator.py using OpenAI TTS.
    """
    if not filename.endswith(".mp3") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    audio_path = SAMPLE_CALLS_DIR / filename
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio file '{filename}' not found. Run ivr_simulator.py option [6] first to generate audio.",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=filename,
    )
