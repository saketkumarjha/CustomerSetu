"""
Duplicate detection service.

After a complaint's embedding is stored, call detect_duplicate_complaints()
to flag semantically similar complaints across any channel (same or different).
Threshold: cosine similarity >= 0.85.
"""

import logging
from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85

# Keep old name as alias so pipeline.py import doesn't need updating
detect_cross_channel_duplicates = None  # reassigned after definition


def resolve_root_parent(complaint_id: str, supabase=None) -> str:
    """
    Follow the merged_into chain to find the ultimate root parent.
    If complaint_id is not merged into anything, it IS the root.
    Guards against cycles with a hop limit.
    """
    if supabase is None:
        supabase = get_supabase()

    current = complaint_id
    for _ in range(10):  # max 10 hops — cycles should never exist but guard anyway
        row = (
            supabase.table("complaints")
            .select("merged_into")
            .eq("complaint_id", current)
            .execute()
        )
        if not row.data:
            break
        parent = row.data[0].get("merged_into")
        if not parent or parent == current:
            break
        current = parent
    return current


def detect_duplicate_complaints(complaint_id: str) -> None:
    """
    Query pgvector for complaints similar to complaint_id (cosine similarity >= 0.85)
    across any channel — same or different. Flag both sides as 'possible_duplicate'
    and append each other's ID to duplicate_of[].

    Skips complaints that are already merged (duplicate_status = 'merged').
    Safe to call multiple times — uses set logic to avoid duplicate entries in the array.
    """
    supabase = get_supabase()

    own = (
        supabase.table("complaints")
        .select("complaint_id, embedding")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not own.data:
        logger.warning("[DEDUP] complaint %s not found", complaint_id)
        return

    row = own.data[0]
    embedding = row.get("embedding")

    if not embedding:
        logger.info("[DEDUP] complaint %s has no embedding yet — skipping", complaint_id)
        return

    # Reuse the existing match_complaints RPC (same function used by duplicate_agent).
    # match_duplicate_complaints does not exist as a Supabase function.
    # We exclude self-comparison in Python after the call.
    try:
        hits = supabase.rpc(
            "match_complaints",
            {
                "query_embedding": embedding,
                "match_threshold": SIMILARITY_THRESHOLD,
                "match_count": 11,  # +1 to account for self being in results
            },
        ).execute()
    except Exception as exc:
        logger.error("[DEDUP] pgvector RPC failed for %s: %s", complaint_id, exc)
        return

    # Exclude self and already-merged complaints.
    # RPC returns {complaint_id, similarity} — fetch duplicate_status separately below.
    raw_hits = [h for h in (hits.data or []) if h["complaint_id"] != complaint_id]
    if not raw_hits:
        logger.info("[DEDUP] no duplicates found for %s", complaint_id)
        return

    raw_ids = [h["complaint_id"] for h in raw_hits]

    # Fetch current state of all matched complaints in one query so we can:
    # 1. Filter out already-merged ones
    # 2. Resolve merged complaints to their root parent
    # 3. Read their current duplicate_of arrays before appending (prevents overwrite)
    matched_rows_resp = (
        supabase.table("complaints")
        .select("complaint_id, duplicate_status, duplicate_of, merged_into")
        .in_("complaint_id", raw_ids)
        .execute()
    )
    matched_rows = {r["complaint_id"]: r for r in (matched_rows_resp.data or [])}

    # For each match: if it's already merged into another complaint, redirect to the
    # root parent so C → B (merged into A) becomes C → A.
    resolved_ids: set[str] = set()
    for cid in raw_ids:
        row = matched_rows.get(cid, {})
        if row.get("duplicate_status") == "merged" and row.get("merged_into"):
            root = resolve_root_parent(row["merged_into"], supabase)
            if root != complaint_id:
                resolved_ids.add(root)
        elif row.get("duplicate_status") != "merged":
            resolved_ids.add(cid)

    similar_ids = list(resolved_ids)

    if not similar_ids:
        logger.info("[DEDUP] no non-merged duplicates found for %s", complaint_id)
        return

    logger.info("[DEDUP] %s flagged as possible duplicate of %s", complaint_id, similar_ids)

    # Update the current complaint's duplicate_of to the full list of matches
    supabase.table("complaints").update({
        "duplicate_status": "possible_duplicate",
        "duplicate_of":     similar_ids,
    }).eq("complaint_id", complaint_id).execute()

    # Reverse-link: append current complaint_id to each matched complaint's duplicate_of.
    # Fetch the current duplicate_of fresh from DB for resolved root parents (they may
    # not be in matched_rows if they differ from the original match IDs).
    roots_resp = (
        supabase.table("complaints")
        .select("complaint_id, duplicate_of, duplicate_status")
        .in_("complaint_id", similar_ids)
        .execute()
    )
    root_rows = {r["complaint_id"]: r for r in (roots_resp.data or [])}

    for sim_id in similar_ids:
        row = root_rows.get(sim_id, {})
        if row.get("duplicate_status") == "merged":
            continue  # root itself got merged in a race — skip
        existing_ids: list = row.get("duplicate_of") or []
        if complaint_id not in existing_ids:
            supabase.table("complaints").update({
                "duplicate_status": "possible_duplicate",
                "duplicate_of":     existing_ids + [complaint_id],
            }).eq("complaint_id", sim_id).execute()


# Backward-compat alias used by pipeline.py
detect_cross_channel_duplicates = detect_duplicate_complaints
