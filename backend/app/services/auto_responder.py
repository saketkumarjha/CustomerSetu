"""
Tiered Auto-Response System

4 tiers based on confidence score + safety checks:

TIER 1 — Full Auto-Send (confidence >= 0.95)
  Customer ko direct response jaata hai
  No human involvement
  Conditions: low severity + no RBI flag + calm/concerned sentiment

TIER 2 — Shadow Mode (confidence 0.80-0.95)
  Customer ko auto-send hota hai
  Human agent ko notification milti hai
  Agent 1 hour mein override kar sakta hai
  If override → apology send hoti hai customer ko

TIER 3 — Human Review Queue (confidence 0.70-0.80)
  Normal human review
  Agent accept/edit/reject karta hai

TIER 4 — Priority Human Review (confidence < 0.70)
  Urgent flag
  Senior agent assign hota hai
  SLA half ho jaata hai
"""

from datetime import datetime, timezone, timedelta
from app.db.supabase_client import get_supabase


# Sentiments jo auto-send ke liye safe hain
SAFE_SENTIMENTS_FOR_AUTO = {"Calm", "Concerned"}

# Yeh categories KABHI auto-send nahi hongi
NEVER_AUTO_SEND_CATEGORIES = {
    "UNAUTHORIZED_TRANSACTION_FRAUD",
    "RECOVERY_AGENT_HARASSMENT",
    "UNSOLICITED_CARD_ISSUANCE",
    "MIS_SELLING_OF_PRODUCTS",
    "DELAY_IN_PROPERTY_DOC_RELEASE",
    "CREDIT_BUREAU_MISREPORTING",
}

# Shadow mode mein agent ke paas kitna time hai override ke liye
SHADOW_OVERRIDE_WINDOW_HOURS = 1


def determine_response_tier(
    confidence_score: float,
    severity: int,
    sentiment: str,
    is_rbi_reportable: bool,
    compliance_category: str,
    grounding_score: float,
    grounding_assessment: str,
) -> dict:
    """
    Confidence + safety checks ke basis pe tier decide karo.

    Returns:
        tier:        "full_auto" | "shadow" | "human_review" | "priority_human"
        tier_number: 1 | 2 | 3 | 4
        can_auto:    bool
        reason:      kyun yeh tier assign hua
        sla_hours:   is tier ke liye SLA
    """

    # ── Safety checks — override karte hain confidence ko ─────────────────
    safety_blocks = []

    if is_rbi_reportable:
        safety_blocks.append("RBI reportable complaint — auto-send blocked")

    if compliance_category in NEVER_AUTO_SEND_CATEGORIES:
        safety_blocks.append(f"{compliance_category} — mandatory human review")

    if severity >= 4:
        safety_blocks.append(f"Severity {severity}/5 — too high for auto-send")

    if sentiment not in SAFE_SENTIMENTS_FOR_AUTO and confidence_score < 0.95:
        safety_blocks.append(f"Sentiment '{sentiment}' — human empathy needed")

    if grounding_assessment == "DO_NOT_SEND":
        safety_blocks.append("Grounding check failed — draft has issues")

    if grounding_score < 0.60:
        safety_blocks.append(f"Low grounding score ({grounding_score:.0%})")

    # ── Safety block hai → directly human review ──────────────────────────
    if safety_blocks:
        if confidence_score < 0.70:
            return {
                "tier": "priority_human",
                "tier_number": 4,
                "can_auto": False,
                "reason": f"Safety blocks + low confidence. Issues: {'; '.join(safety_blocks)}",
                "sla_hours": 4,      # half the normal SLA
                "safety_blocks": safety_blocks,
            }
        return {
            "tier": "human_review",
            "tier_number": 3,
            "can_auto": False,
            "reason": f"Safety blocks present. Issues: {'; '.join(safety_blocks)}",
            "sla_hours": 24,
            "safety_blocks": safety_blocks,
        }

    # ── No safety blocks → confidence pe tier decide karo ─────────────────

    if confidence_score >= 0.95:
        return {
            "tier": "full_auto",
            "tier_number": 1,
            "can_auto": True,
            "reason": (
                f"Confidence {confidence_score:.0%} >= 95% threshold. "
                f"Severity {severity}/5. Sentiment: {sentiment}. "
                f"No RBI flags. Full auto-send approved."
            ),
            "sla_hours": 1,
            "safety_blocks": [],
        }

    if confidence_score >= 0.80:
        return {
            "tier": "shadow",
            "tier_number": 2,
            "can_auto": True,
            "reason": (
                f"Confidence {confidence_score:.0%} — 80-95% range. "
                f"Auto-sending with {SHADOW_OVERRIDE_WINDOW_HOURS}hr human override window."
            ),
            "sla_hours": 2,
            "safety_blocks": [],
        }

    if confidence_score >= 0.70:
        return {
            "tier": "human_review",
            "tier_number": 3,
            "can_auto": False,
            "reason": (
                f"Confidence {confidence_score:.0%} — 70-80% range. "
                f"Human review required."
            ),
            "sla_hours": 24,
            "safety_blocks": [],
        }

    # confidence < 0.70
    return {
        "tier": "priority_human",
        "tier_number": 4,
        "can_auto": False,
        "reason": (
            f"Confidence {confidence_score:.0%} < 70%. "
            f"Low confidence — priority human review flagged."
        ),
        "sla_hours": 4,
        "safety_blocks": [],
    }


def execute_auto_response(
    complaint_id: str,
    customer_id: str,
    channel: str,
    draft_response: str,
    tier: str,
    confidence_score: float,
) -> dict:
    """
    Auto-response execute karo based on tier.

    TIER 1 (full_auto):
      → Customer ko send karo
      → Status: closed
      → CSAT survey schedule karo

    TIER 2 (shadow):
      → Customer ko send karo
      → Human agent ko notification
      → Override deadline set karo
      → Status: shadow_sent

    TIER 3/4 (human_review / priority_human):
      → Yeh function call nahi hoga — router handle karta hai
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    if tier == "full_auto":
        # ── Simulate send karo (POC) ───────────────────────────────────────
        _simulate_send_to_customer(
            customer_id=customer_id,
            channel=channel,
            draft_response=draft_response,
            send_type="FULL_AUTO",
            complaint_id=complaint_id,
        )

        # ── DB update ─────────────────────────────────────────────────────
        supabase.table("complaints").update({
            "status": "auto_closed",
            "pipeline_status": "complete",
            "response_tier": "full_auto",
            "auto_sent_at": now.isoformat(),
        }).eq("complaint_id", complaint_id).execute()

        # ── Fine-tune dataset mein save karo ──────────────────────────────
        _save_auto_response_to_dataset(
            complaint_id=complaint_id,
            draft_response=draft_response,
            tier=tier,
            agent_score=1.0,   # auto-sent = highest confidence
        )

        return {
            "action_taken": "full_auto_sent",
            "sent_to_customer": True,
            "human_notified": False,
            "status": "auto_closed",
            "message": f"Response auto-sent to customer via {channel}.",
        }

    elif tier == "shadow":
        # ── Customer ko send karo ─────────────────────────────────────────
        _simulate_send_to_customer(
            customer_id=customer_id,
            channel=channel,
            draft_response=draft_response,
            send_type="SHADOW_AUTO",
            complaint_id=complaint_id,
        )

        override_deadline = now + timedelta(hours=SHADOW_OVERRIDE_WINDOW_HOURS)

        # ── Human agent ko notify karo ────────────────────────────────────
        _notify_human_agent(
            complaint_id=complaint_id,
            draft_response=draft_response,
            confidence_score=confidence_score,
            override_deadline=override_deadline,
        )

        # ── DB update ─────────────────────────────────────────────────────
        supabase.table("complaints").update({
            "status": "shadow_sent",
            "pipeline_status": "complete",
            "response_tier": "shadow",
            "auto_sent_at": now.isoformat(),
            "shadow_override_deadline": override_deadline.isoformat(),
            "shadow_overridden": False,
        }).eq("complaint_id", complaint_id).execute()

        return {
            "action_taken": "shadow_auto_sent",
            "sent_to_customer": True,
            "human_notified": True,
            "override_deadline": override_deadline.isoformat(),
            "override_window_hours": SHADOW_OVERRIDE_WINDOW_HOURS,
            "status": "shadow_sent",
            "message": (
                f"Response auto-sent to customer. "
                f"Human agent has {SHADOW_OVERRIDE_WINDOW_HOURS}hr to override."
            ),
        }

    return {"action_taken": "none", "sent_to_customer": False}


def execute_shadow_override(
    complaint_id: str,
    agent_id: str,
    corrected_response: str,
    override_reason: str,
) -> dict:
    """
    Shadow mode mein human agent override karta hai.

    Steps:
    1. Check karo ki override window abhi valid hai
    2. Customer ko corrected response send karo
    3. Apology note bhi send karo (auto-send was wrong)
    4. DB update karo
    5. Penalty: auto-sent draft ko negative score do dataset mein
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    # Complaint fetch karo
    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, status, shadow_override_deadline, "
            "shadow_overridden, customer_id, channel, draft_response"
        )
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    complaint = result.data[0]

    # Status check
    if complaint.get("status") != "shadow_sent":
        raise ValueError(
            f"Complaint is not in shadow mode. "
            f"Current status: {complaint.get('status')}"
        )

    # Override already hua?
    if complaint.get("shadow_overridden"):
        raise ValueError("Shadow override already applied for this complaint")

    # Override window check
    deadline_str = complaint.get("shadow_override_deadline")
    if deadline_str:
        deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        if now > deadline:
            raise ValueError(
                f"Override window expired at {deadline.isoformat()}. "
                f"Cannot override after {SHADOW_OVERRIDE_WINDOW_HOURS} hours."
            )

    # ── Corrected response send karo ──────────────────────────────────────
    _simulate_send_to_customer(
        customer_id=complaint.get("customer_id", ""),
        channel=complaint.get("channel", "web"),
        draft_response=corrected_response,
        send_type="SHADOW_OVERRIDE_CORRECTION",
        complaint_id=complaint_id,
    )

    # ── DB update ─────────────────────────────────────────────────────────
    supabase.table("complaints").update({
        "status": "override_closed",
        "shadow_overridden": True,
    }).eq("complaint_id", complaint_id).execute()

    # ── Agent feedback store karo ─────────────────────────────────────────
    supabase.table("agent_feedback").insert({
        "complaint_id": complaint_id,
        "agent_id": agent_id,
        "action": "edit",
        "original_draft": complaint.get("draft_response", ""),
        "final_response": corrected_response,
        "agent_score": 0.5,   # edit = 0.5
    }).execute()

    # ── Dataset mein negative signal ──────────────────────────────────────
    # Auto-sent draft wrong tha — dataset mein 0.0 score
    _save_auto_response_to_dataset(
        complaint_id=complaint_id,
        draft_response=complaint.get("draft_response", ""),
        tier="shadow_overridden",
        agent_score=0.0,
    )

    return {
        "complaint_id": complaint_id,
        "override_applied": True,
        "corrected_response_sent": True,
        "agent_id": agent_id,
        "override_reason": override_reason,
        "message": "Override applied. Corrected response sent to customer.",
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _simulate_send_to_customer(
    customer_id: str,
    channel: str,
    draft_response: str,
    send_type: str,
    complaint_id: str,
) -> None:
    """
    POC mein simulate karte hain — logs mein print karte hain.
    Production mein: SendGrid (email), Twilio (SMS/WhatsApp), WebSocket (web)
    """
    print(f"\n{'='*60}")
    print(f"[AUTO-SEND] Type: {send_type}")
    print(f"[AUTO-SEND] Complaint: {complaint_id}")
    print(f"[AUTO-SEND] Customer: {customer_id}")
    print(f"[AUTO-SEND] Channel: {channel}")
    print(f"[AUTO-SEND] Response preview: {draft_response[:100]}...")
    print(f"[AUTO-SEND] Would send via: "
          f"{'SendGrid Email' if channel == 'email' else 'Twilio WhatsApp' if channel == 'whatsapp' else 'Web Notification'}")
    print(f"{'='*60}\n")


def _notify_human_agent(
    complaint_id: str,
    draft_response: str,
    confidence_score: float,
    override_deadline: datetime,
) -> None:
    """
    Shadow mode mein human agent ko notify karo.
    Production mein: Email/Slack/Dashboard notification.
    """
    print(f"\n{'='*60}")
    print(f"[SHADOW NOTIFY] Complaint: {complaint_id}")
    print(f"[SHADOW NOTIFY] Confidence: {confidence_score:.0%}")
    print(f"[SHADOW NOTIFY] Auto-sent to customer.")
    print(f"[SHADOW NOTIFY] You have until {override_deadline.strftime('%H:%M UTC')} to override.")
    print(f"[SHADOW NOTIFY] Override: POST /api/v1/complaints/{complaint_id}/shadow-override")
    print(f"{'='*60}\n")


def _save_auto_response_to_dataset(
    complaint_id: str,
    draft_response: str,
    tier: str,
    agent_score: float,
) -> None:
    """Auto-send kiye gaye responses ko fine-tune dataset mein save karo."""
    supabase = get_supabase()
    try:
        complaint = (
            supabase.table("complaints")
            .select("masked_text, category")
            .eq("complaint_id", complaint_id)
            .execute()
        )
        if complaint.data:
            supabase.table("fine_tune_dataset").insert({
                "complaint_id": complaint_id,
                "complaint_text": complaint.data[0].get("masked_text", ""),
                "ai_draft": draft_response,
                "agent_corrected_response": draft_response,
                "agent_rating": agent_score,
                "category": complaint.data[0].get("category", "General Banking"),
                "exported": False,
            }).execute()
    except Exception as e:
        print(f"[DATASET] Save failed: {e}")