"""
XAI (Explainable AI) endpoint.

Returns the full explanation trace for a complaint —
one entry per agent with decision, confidence, reasoning, and evidence.
This is what your frontend renders in the pipeline step visualization.
"""

from fastapi import APIRouter, HTTPException, status, Path
from app.db.supabase_client import get_supabase

router = APIRouter()


@router.get(
    "/{complaint_id}/explanation",
    summary="Get full XAI explanation trace for a complaint",
    responses={404: {"description": "Complaint not found"}},
)
async def get_explanation(complaint_id: str = Path(..., pattern=r"^CMP-[0-9A-F]{8}$", description="Complaint ID (format: CMP-XXXXXXXX)")):
    """
    Returns all agent decisions for a complaint in pipeline order.

    Response maps directly to your frontend's pipeline step visualization:
    - agent_name → step label
    - status → Complete / Processing / Failed
    - decision → main output value
    - confidence → confidence bar
    - reasoning → expandable "Why?" section
    - evidence → highlighted keywords
    """
    supabase = get_supabase()

    # Verify complaint exists
    complaint_result = (
        supabase.table("complaints")
        .select("complaint_id, pipeline_status, route, category, severity")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not complaint_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint {complaint_id} not found."
        )

    # Fetch all agent decisions in pipeline order
    decisions_result = (
        supabase.table("agent_decisions")
        .select("*")
        .eq("complaint_id", complaint_id)
        .order("agent_order")
        .execute()
    )

    complaint = complaint_result.data[0]
    decisions = decisions_result.data or []

    return {
        "complaint_id": complaint_id,
        "pipeline_status": complaint.get("pipeline_status"),
        "final_route": complaint.get("route"),
        "category": complaint.get("category"),
        "severity": complaint.get("severity"),
        "total_agents": len(decisions),
"explanation_trace": decisions,
    }