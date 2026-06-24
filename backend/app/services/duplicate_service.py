"""
Cross-channel duplicate detection service.

After a complaint's embedding is stored, call detect_cross_channel_duplicates()
to flag semantically similar complaints from different channels.
Threshold: cosine similarity >= 0.85.
"""

import logging
from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85


def detect_cross_channel_duplicates(complaint_id: str) -> None:
    """
    Query pgvector for complaints similar to complaint_id (cosine similarity >= 0.85)
    filed on a different channel. Flag both sides as 'possible_duplicate' and
    append each other's ID to duplicate_of[].

    Skips complaints that are already merged (duplicate_status = 'merged').
    Safe to call multiple times — uses set logic to avoid duplicate entries in the array.
    """
    supabase = get_supabase()

    own = (
        supabase.table("complaints")
        .select("complaint_id, channel, embedding")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not own.data:
        logger.warning("[DEDUP] complaint %s not found", complaint_id)
        return

    row = own.data[0]
    embedding = row.get("embedding")
    channel = row.get("channel")

    if not embedding:
        logger.info("[DEDUP] complaint %s has no embedding yet — skipping", complaint_id)
        return

    try:
        hits = supabase.rpc(
            "match_cross_channel_complaints",
            {
                "query_embedding": embedding,
                "match_threshold": SIMILARITY_THRESHOLD,
                "match_count": 10,
                "exclude_id": complaint_id,
                "exclude_channel": channel,
            },
        ).execute()
    except Exception as exc:
        logger.error("[DEDUP] pgvector RPC failed for %s: %s", complaint_id, exc)
        return

    similar = [
        h for h in (hits.data or [])
        if h.get("duplicate_status") != "merged"
    ]

    if not similar:
        logger.info("[DEDUP] no cross-channel duplicates found for %s", complaint_id)
        return

    similar_ids = [h["complaint_id"] for h in similar]
    logger.info("[DEDUP] %s flagged as possible duplicate of %s", complaint_id, similar_ids)

    supabase.table("complaints").update({
        "duplicate_status": "possible_duplicate",
        "duplicate_of":     similar_ids,
    }).eq("complaint_id", complaint_id).execute()

    for hit in similar:
        existing_ids: list = hit.get("duplicate_of") or []
        if complaint_id not in existing_ids:
            supabase.table("complaints").update({
                "duplicate_status": "possible_duplicate",
                "duplicate_of":     existing_ids + [complaint_id],
            }).eq("complaint_id", hit["complaint_id"]).execute()
