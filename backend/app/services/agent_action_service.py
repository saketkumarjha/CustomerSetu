"""
Agent Action Service — Handle the 4 human-agent review actions.

  ACCEPT         → send AI draft as-is, close complaint
  EDIT           → send edited response, close complaint
  REJECT         → discard AI draft, agent must write manually
  MANUAL_ESCALATE → override Agent 10.5, re-run pipeline at higher tier
"""

from datetime import datetime, timezone
from app.db.supabase_client import get_supabase
from app.services.queue_service import complete_queue_entry
from app.services.status_service import update_status
from app.services.metrics_service import track_review_completed


# ── Shared helpers ────────────────────────────────────────────────────────────

def _log_feedback(
    complaint_id: str,
    agent_id: str,
    action_type: str,
    original_draft: str,
    agent_output: str,
    confidence_at_review: float,
    feedback_score: float,
    time_spent_seconds: int | None = None,
) -> None:
    supabase = get_supabase()
    try:
        supabase.table("agent_feedback").insert({
            "complaint_id":   complaint_id,
            "agent_id":       agent_id,
            "action":         action_type,
            "original_draft": original_draft,
            "final_response": agent_output,
            "agent_score":    feedback_score,
        }).execute()
    except Exception:
        pass  # non-critical audit log — do not block the action


def _simulate_send(customer_id: str, channel: str, response: str, complaint_id: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    print(f"\n[AGENT ACTION] Sending to customer {customer_id} via {channel}")
    print(f"[AGENT ACTION] Complaint: {complaint_id}")
    print(f"[AGENT ACTION] Response: {response[:120]}...")
    return now


def _get_complaint(complaint_id: str) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, customer_id, channel, draft_response, "
            "confidence_score, current_tier, assigned_agent_id"
        )
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Complaint {complaint_id} not found")
    return result.data[0]


# ── Action handlers ───────────────────────────────────────────────────────────

def handle_accept(complaint_id: str, agent_id: str, notes: str = "") -> dict:
    """Agent approves the AI draft and sends it to the customer."""
    supabase = get_supabase()
    c = _get_complaint(complaint_id)

    draft = c.get("draft_response", "")
    confidence = c.get("confidence_score") or 0.0
    channel = c.get("channel", "web")
    customer_id = c.get("customer_id", "")

    sent_at = _simulate_send(customer_id, channel, draft, complaint_id)

    # Transition status first so update_status reads the correct current status
    update_status(complaint_id, "auto_closed", changed_by=agent_id,
                  metadata={"action": "ACCEPT"})

    supabase.table("complaints").update({
        "pipeline_status":         "complete",
        "final_response_text":     draft,
        "response_sent_at":        sent_at,
        "response_channel":        channel,
        "agent_action":            "ACCEPT",
        "agent_notes":             notes,
    }).eq("complaint_id", complaint_id).execute()
    track_review_completed(complaint_id, agent_id, "ACCEPT")
    _log_feedback(
        complaint_id=complaint_id,
        agent_id=agent_id,
        action_type="ACCEPT",
        original_draft=draft,
        agent_output=draft,
        confidence_at_review=confidence,
        feedback_score=1.0,
    )

    # Enqueue for KB enrichment with full quality signals
    try:
        from app.services.resolution_event_handler import resolution_event_handler
        resolution_event_handler.on_agent_action(
            complaint_id = complaint_id,
            agent_id     = agent_id,
            action       = "ACCEPT",
        )
    except Exception:
        pass

    return {
        "complaint_id": complaint_id,
        "action": "ACCEPT",
        "response_sent": True,
        "sent_at": sent_at,
        "status": "auto_closed",
        "message": "AI draft accepted and sent to customer.",
    }


def handle_edit(
    complaint_id: str,
    agent_id: str,
    edited_response: str,
    notes: str = "",
) -> dict:
    """Agent modifies the AI draft and sends the edited version."""
    supabase = get_supabase()
    c = _get_complaint(complaint_id)

    original_draft = c.get("draft_response", "")
    confidence = c.get("confidence_score") or 0.0
    channel = c.get("channel", "web")
    customer_id = c.get("customer_id", "")

    sent_at = _simulate_send(customer_id, channel, edited_response, complaint_id)

    # Transition status first so update_status reads the correct current status
    update_status(complaint_id, "auto_closed", changed_by=agent_id,
                  metadata={"action": "EDIT"})

    supabase.table("complaints").update({
        "pipeline_status":           "complete",
        "final_response_text":       edited_response,
        "response_sent_at":          sent_at,
        "response_channel":          channel,
        "agent_action":              "EDIT",
        "agent_notes":               notes,
    }).eq("complaint_id", complaint_id).execute()
    track_review_completed(complaint_id, agent_id, "EDIT")
    _log_feedback(
        complaint_id=complaint_id,
        agent_id=agent_id,
        action_type="EDIT",
        original_draft=original_draft,
        agent_output=edited_response,
        confidence_at_review=confidence,
        feedback_score=0.5,
    )

    # Enqueue for KB enrichment with edited response and quality signals
    try:
        from app.services.resolution_event_handler import resolution_event_handler
        resolution_event_handler.on_agent_action(
            complaint_id = complaint_id,
            agent_id     = agent_id,
            action       = "EDIT",
            action_data  = {"edited_response": edited_response, "notes": notes},
        )
    except Exception:
        pass

    return {
        "complaint_id": complaint_id,
        "action": "EDIT",
        "response_sent": True,
        "sent_at": sent_at,
        "status": "auto_closed",
        "message": "Edited response sent to customer.",
    }


def handle_reject(
    complaint_id: str,
    agent_id: str,
    rejection_reason: str,
    notes: str = "",
) -> dict:
    """Agent rejects the AI draft. Complaint moves to awaiting_agent_response."""
    supabase = get_supabase()
    c = _get_complaint(complaint_id)

    original_draft = c.get("draft_response", "")
    confidence = c.get("confidence_score") or 0.0

    # Transition status first so update_status reads the correct current status
    update_status(complaint_id, "awaiting_agent_response", changed_by=agent_id,
                  metadata={"action": "REJECT", "reason": rejection_reason})

    supabase.table("complaints").update({
        "agent_action": "REJECT",
        "agent_notes":  notes,
    }).eq("complaint_id", complaint_id).execute()
    track_review_completed(complaint_id, agent_id, "REJECT")
    _log_feedback(
        complaint_id=complaint_id,
        agent_id=agent_id,
        action_type="REJECT",
        original_draft=original_draft,
        agent_output="",
        confidence_at_review=confidence,
        feedback_score=0.0,
    )

    return {
        "complaint_id": complaint_id,
        "action": "REJECT",
        "response_sent": False,
        "status": "awaiting_agent_response",
        "message": (
            "AI draft rejected. Please provide a manual response. "
            "Complaint is now in 'awaiting_agent_response' status."
        ),
    }


def handle_manual_escalate(
    complaint_id: str,
    agent_id: str,
    target_tier: int,
    reason: str,
    notes: str = "",
) -> dict:
    """
    Agent overrides Agent 10.5 and escalates to target_tier.

    Re-triggers the pipeline at the new tier so Agent 7+8 generate a fresh
    resolution. The result may auto-respond or land back in the human queue.
    """
    supabase = get_supabase()
    c = _get_complaint(complaint_id)
    now = datetime.now(timezone.utc)

    original_draft = c.get("draft_response", "")
    confidence = c.get("confidence_score") or 0.0
    from_tier = c.get("current_tier", 1)

    # Log escalation history
    supabase.table("complaint_escalation_history").insert({
        "complaint_id":      complaint_id,
        "from_tier":         from_tier,
        "to_tier":           target_tier,
        "escalated_by":      "HUMAN",
        "escalation_reason": "MANUAL",
        "agent_reasoning":   reason,
        "agent_id":          agent_id,
        "escalated_at":      now.isoformat(),
    }).execute()

    # Transition status first so update_status reads the correct current status
    update_status(complaint_id, "escalating", changed_by=agent_id,
                  metadata={"action": "MANUAL_ESCALATE", "target_tier": target_tier})

    # Update complaint tier fields after status transition
    supabase.table("complaints").update({
        "current_tier":  target_tier,
        "assigned_tier": target_tier,
        "agent_action":  "MANUAL_ESCALATE",
        "agent_notes":   notes,
    }).eq("complaint_id", complaint_id).execute()
    track_review_completed(complaint_id, agent_id, "ESCALATE")
    _log_feedback(
        complaint_id=complaint_id,
        agent_id=agent_id,
        action_type="ESCALATE",
        original_draft=original_draft,
        agent_output="",
        confidence_at_review=confidence,
        feedback_score=-0.5,
    )

    return {
        "complaint_id": complaint_id,
        "action": "MANUAL_ESCALATE",
        "from_tier": from_tier,
        "target_tier": target_tier,
        "response_sent": False,
        "status": "escalating",
        "pipeline_re_run_required": True,
        "message": (
            f"Complaint escalated from Tier {from_tier} to Tier {target_tier} by agent. "
            f"Re-run the pipeline to generate a new resolution at the higher tier."
        ),
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _schedule_kb_add(
    complaint_id: str,
    resolution_text: str,
    quality_score: float,
    human_verified: bool = False,
) -> None:
    """Queue resolution for knowledge-base addition (best-effort, non-blocking)."""
    from datetime import timedelta
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    supabase.table("kb_enrichment_queue").insert({
        "complaint_id":   complaint_id,
        "resolution_text": resolution_text,
        "scheduled_for":  now.isoformat(),
        "processed":      False,
        "added_to_kb":    False,
    }).execute()
