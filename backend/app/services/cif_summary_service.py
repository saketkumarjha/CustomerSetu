"""
CIF Summary Service — roll up per-complaint digests into a customer narrative.

Called by APScheduler every 1 minute.
Reads dirty cif_ids, stitches complaint_summary rows, calls gpt-4o-mini,
writes the narrative back to cif_summaries.
"""
import logging
from datetime import datetime, timezone
from openai import OpenAI
from app.db.supabase_client import get_supabase
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior bank complaints analyst. "
    "Below are short summaries of all complaints filed by one customer, oldest first. "
    "Write a 2–4 sentence narrative for a human agent that covers: "
    "(1) the pattern of issues the customer has experienced, "
    "(2) how previous complaints were resolved, "
    "(3) the customer's sentiment trajectory, "
    "(4) practical advice for handling the current complaint. "
    "Be professional, specific, and under 100 words. Do not invent facts."
)


async def refresh_dirty_cif_summaries() -> dict:
    """
    Find all CIFs marked dirty, regenerate their narrative summaries, clear dirty flag.
    Returns {"processed": N, "errors": N}.
    """
    supabase = get_supabase()
    settings = get_settings()

    dirty_resp = (
        supabase.table("cif_summaries")
        .select("cif_id")
        .eq("dirty", True)
        .execute()
    )
    dirty_rows = dirty_resp.data or []

    if not dirty_rows:
        return {"processed": 0, "errors": 0}

    client = OpenAI(api_key=settings.openai_api_key)
    processed = 0
    errors = 0

    for row in dirty_rows:
        cif_id = row["cif_id"]
        try:
            comp_resp = (
                supabase.table("complaints")
                .select("complaint_summary, created_at, category")
                .eq("cif_id", cif_id)
                .not_.is_("complaint_summary", "null")
                .order("created_at", desc=False)
                .execute()
            )
            summaries = comp_resp.data or []

            if not summaries:
                supabase.table("cif_summaries").update({"dirty": False}).eq("cif_id", cif_id).execute()
                continue

            lines = [
                f"{i+1}. [{s.get('category') or 'Unknown'}] {s['complaint_summary']}"
                for i, s in enumerate(summaries)
            ]
            user_msg = "\n".join(lines)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=160,
                temperature=0.3,
            )
            narrative = response.choices[0].message.content.strip()

            supabase.table("cif_summaries").upsert(
                {
                    "cif_id": cif_id,
                    "summary_text": narrative,
                    "complaint_count": len(summaries),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "dirty": False,
                },
                on_conflict="cif_id",
            ).execute()

            logger.info("[CIF_SUMMARY] regenerated narrative for cif=%s (%d complaints)", cif_id, len(summaries))
            processed += 1

        except Exception as exc:
            logger.error("[CIF_SUMMARY] failed for cif=%s: %s", cif_id, exc)
            errors += 1

    return {"processed": processed, "errors": errors}
