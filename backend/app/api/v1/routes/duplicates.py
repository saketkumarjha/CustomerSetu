"""
Duplicate complaint management endpoints.

POST /merge                       — agent confirms merge (primary wins, secondary hidden)
POST /{id}/confirm-same-person    — agent unlocks merge for different-CIF pairs
"""

import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.db.supabase_client import get_supabase
from app.services.duplicate_service import resolve_root_parent

logger = logging.getLogger(__name__)
router = APIRouter()


class MergeRequest(BaseModel):
    primary_id: str
    secondary_id: str


@router.post(
    "/merge",
    summary="Merge secondary complaint into primary (agent action)",
    status_code=status.HTTP_200_OK,
)
def merge_complaints(body: MergeRequest):
    """
    Agent selects which complaint is primary. Secondary gets merged_into set
    and duplicate_status='merged'. It will no longer appear in the main table.

    Rules:
    - Same CIF: merge allowed immediately
    - Different CIF: both must already have duplicate_status='confirmed_duplicate'
    """
    supabase = get_supabase()

    primary = supabase.table("complaints").select(
        "complaint_id, cif_id, duplicate_status"
    ).eq("complaint_id", body.primary_id).execute()

    secondary = supabase.table("complaints").select(
        "complaint_id, cif_id, duplicate_status"
    ).eq("complaint_id", body.secondary_id).execute()

    if not primary.data:
        raise HTTPException(status_code=404, detail=f"Primary complaint {body.primary_id} not found")
    if not secondary.data:
        raise HTTPException(status_code=404, detail=f"Secondary complaint {body.secondary_id} not found")

    p = primary.data[0]
    s = secondary.data[0]

    same_cif = (p.get("cif_id") and p.get("cif_id") == s.get("cif_id"))
    if not same_cif:
        if s.get("duplicate_status") != "confirmed_duplicate" or p.get("duplicate_status") != "confirmed_duplicate":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Different-CIF merge requires confirm-same-person on both complaints first.",
            )

    # Always merge into the root parent — if primary_id is itself merged into
    # another complaint, follow the chain so merged_into always points to the root.
    root_primary = resolve_root_parent(body.primary_id)
    if root_primary != body.primary_id:
        logger.info("[DEDUP] primary %s is merged — redirecting merge target to root %s", body.primary_id, root_primary)

    supabase.table("complaints").update({
        "merged_into":      root_primary,
        "duplicate_status": "merged",
    }).eq("complaint_id", body.secondary_id).execute()

    logger.info("[DEDUP] Merged %s into %s (root: %s)", body.secondary_id, body.primary_id, root_primary)
    return {"status": "merged", "primary_id": root_primary, "secondary_id": body.secondary_id}


@router.post(
    "/{complaint_id}/confirm-same-person",
    summary="Agent confirms two different-CIF complaints are from the same person",
    status_code=status.HTTP_200_OK,
)
def confirm_same_person(complaint_id: str):
    """
    Sets duplicate_status='confirmed_duplicate' on this complaint and all
    complaints listed in its duplicate_of[] that have a different cif_id.
    This unlocks the merge button on the frontend.
    """
    supabase = get_supabase()

    own = supabase.table("complaints").select(
        "complaint_id, cif_id, duplicate_of"
    ).eq("complaint_id", complaint_id).execute()

    if not own.data:
        raise HTTPException(status_code=404, detail=f"Complaint {complaint_id} not found")

    row = own.data[0]
    own_cif = row.get("cif_id")
    related_ids: list = row.get("duplicate_of") or []

    supabase.table("complaints").update({
        "duplicate_status": "confirmed_duplicate"
    }).eq("complaint_id", complaint_id).execute()

    for rel_id in related_ids:
        rel = supabase.table("complaints").select(
            "complaint_id, cif_id"
        ).eq("complaint_id", rel_id).execute()

        if rel.data and rel.data[0].get("cif_id") != own_cif:
            supabase.table("complaints").update({
                "duplicate_status": "confirmed_duplicate"
            }).eq("complaint_id", rel_id).execute()

    logger.info("[DEDUP] confirm-same-person: %s and related %s", complaint_id, related_ids)
    return {"status": "confirmed", "complaint_id": complaint_id}
