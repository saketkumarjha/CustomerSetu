import time
from typing import Optional, Any
from app.db.supabase_client import get_supabase
from app.models.agent_output import AgentOutput, AgentStatus


async def write_agent_decision(
    complaint_id: str,
    agent_output: AgentOutput
) -> None:
    """
    Persist one agent's decision to the agent_decisions table.

    Called by every agent after it completes.
    One row per agent per complaint.
    This powers:
    1. Your frontend's pipeline step visualization
    2. The XAI explanation endpoint
    3. The audit trail for compliance
    """
    supabase = get_supabase()

    record = {
        "complaint_id": complaint_id,
        "agent_name": agent_output.agent_name,
        "agent_order": agent_output.agent_order,
        "status": agent_output.status.value,
        "decision": agent_output.decision,
        "confidence": agent_output.confidence,
        "reasoning": agent_output.reasoning,
        "evidence": agent_output.evidence or [],
        "metadata": agent_output.metadata or {},
        "error_message": agent_output.error_message,
        "duration_ms": agent_output.duration_ms,
    }

    try:
        supabase.table("agent_decisions").insert(record).execute()
    except Exception as e:
        # Audit trail failure must NOT crash the pipeline
        print(f"[AUDIT] Failed to write agent decision: {e}")


async def mark_agent_processing(
    complaint_id: str,
    agent_name: str,
    agent_order: int
) -> None:
    """
    Insert a 'processing' row at the START of an agent's execution.
    The SSE frontend shows this immediately as the spinning indicator.
    Updated to 'complete' or 'failed' when agent finishes.
    """
    supabase = get_supabase()

    record = {
        "complaint_id": complaint_id,
        "agent_name": agent_name,
        "agent_order": agent_order,
        "status": AgentStatus.PROCESSING.value,
    }

    try:
        supabase.table("agent_decisions").insert(record).execute()
    except Exception as e:
        print(f"[AUDIT] Failed to mark agent processing: {e}")


async def update_complaint_status(
    complaint_id: str,
    status: str,
    extra_fields: Optional[dict[str, Any]] = None
) -> None:
    """
    Update the complaints table with pipeline progress.
    Called at key stages: start, after routing, on completion.
    """
    supabase = get_supabase()

    update_data = {"pipeline_status": status, "status": status}
    if extra_fields:
        update_data.update(extra_fields)

    try:
        supabase.table("complaints").update(update_data).eq(
            "complaint_id", complaint_id
        ).execute()
    except Exception as e:
        print(f"[AUDIT] Failed to update complaint status: {e}")