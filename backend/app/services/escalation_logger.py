"""
Escalation Logger

Writes to complaint_escalation_history and atomically updates
complaint.escalation_count / escalation_path / current_tier / is_escalating.
"""

import json
from datetime import datetime, timezone
from app.db.supabase_client import get_supabase


def log_escalation(
    complaint_id: str,
    from_tier: int,
    to_tier: int,
    escalation_reason: str,
    confidence_before: float = None,
    kb_coverage_before: float = None,
    tier_response_text: str = None,
    tier_knowledge_used: list = None,
    escalation_decision_reasoning: str = None,
    signals_detected: list = None,
    agent_outputs_snapshot: dict = None,
) -> dict:
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    history_row: dict = {
        "complaint_id": complaint_id,
        "from_tier": from_tier,
        "to_tier": to_tier,
        "escalated_by": "SYSTEM",
        "escalation_reason": escalation_reason,
        "escalated_at": now.isoformat(),
        "status": "in_progress",
    }

    if confidence_before is not None:
        history_row["confidence_before"] = confidence_before
    if kb_coverage_before is not None:
        history_row["kb_coverage_before"] = kb_coverage_before
    if tier_response_text:
        history_row["tier_response_text"] = tier_response_text
    if tier_knowledge_used:
        history_row["tier_knowledge_used"] = tier_knowledge_used
    if escalation_decision_reasoning:
        history_row["escalation_decision_reasoning"] = escalation_decision_reasoning
    if signals_detected:
        history_row["signals_detected"] = signals_detected
    if agent_outputs_snapshot:
        history_row["agent_outputs_snapshot"] = agent_outputs_snapshot

    insert_result = supabase.table("complaint_escalation_history").insert(history_row).execute()
    history_id = insert_result.data[0]["id"] if insert_result.data else None

    # Read current escalation state
    row_result = (
        supabase.table("complaints")
        .select("escalation_count, escalation_path, max_tier_reached")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not row_result.data:
        return {"logged_at": now.isoformat()}

    row = row_result.data[0]
    escalation_count = (row.get("escalation_count") or 0) + 1

    raw_path = row.get("escalation_path") or []
    if isinstance(raw_path, str):
        raw_path = json.loads(raw_path)
    escalation_path = list(raw_path) + [to_tier]

    max_tier = max(row.get("max_tier_reached") or 0, to_tier)

    supabase.table("complaints").update({
        "current_tier": to_tier,
        "escalation_count": escalation_count,
        "escalation_path": escalation_path,
        "max_tier_reached": max_tier,
        "is_escalating": True,
        "last_escalation_at": now.isoformat(),
    }).eq("complaint_id", complaint_id).execute()

    return {
        "escalation_count": escalation_count,
        "escalation_path": escalation_path,
        "logged_at": now.isoformat(),
        "history_id": history_id,
    }


def update_escalation_result(
    history_id: str,
    tier_response_text: str = None,
    tier_knowledge_used: list = None,
    agent_outputs_snapshot: dict = None,
    status: str = "completed",
) -> None:
    """
    Phase-2 write — called after run_tier_transition_pipeline completes.
    Updates the in_progress row with actual pipeline outputs.
    """
    if not history_id:
        return
    supabase = get_supabase()
    payload: dict = {"status": status}
    if tier_response_text:
        payload["tier_response_text"] = tier_response_text
    if tier_knowledge_used is not None:
        payload["tier_knowledge_used"] = tier_knowledge_used
    if agent_outputs_snapshot is not None:
        payload["agent_outputs_snapshot"] = agent_outputs_snapshot
    supabase.table("complaint_escalation_history").update(payload).eq("id", history_id).execute()


def mark_escalation_complete(
    complaint_id: str,
    final_tier: int,
    final_route: str,
) -> None:
    supabase = get_supabase()
    payload: dict = {
        "is_escalating": False,
        "current_tier": final_tier,
    }
    if final_route == "auto_respond":
        payload["status"] = "resolved"
    supabase.table("complaints").update(payload).eq("complaint_id", complaint_id).execute()


def mark_escalation_failed(
    complaint_id: str,
    from_tier: int,
    error: str,
) -> None:
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    supabase.table("complaint_escalation_history").insert({
        "complaint_id": complaint_id,
        "from_tier": from_tier,
        "to_tier": from_tier,
        "escalated_by": "SYSTEM",
        "escalation_reason": "ESCALATION_FAILED",
        "escalated_at": now.isoformat(),
        "escalation_decision_reasoning": f"Error: {error}",
        "status": "failed",
    }).execute()

    supabase.table("complaints").update({
        "is_escalating": False,
    }).eq("complaint_id", complaint_id).execute()
