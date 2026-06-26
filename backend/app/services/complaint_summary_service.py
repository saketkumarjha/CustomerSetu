"""
Complaint Summary Service — generate a 1–3 sentence digest for a single complaint.

Called from routing_node (graph.py) after route decision.
Writes complaint_summary to complaints table and marks cif_summaries dirty.
"""
import logging
from openai import OpenAI
from app.db.supabase_client import get_supabase
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a concise assistant summarising a bank complaint for a human agent. "
    "Write exactly 1–3 sentences covering: (1) complaint category and what went wrong, "
    "(2) how it was or is being handled, (3) customer sentiment. "
    "Be factual, professional, and under 60 words. Do not include customer names or account numbers."
)


def generate_complaint_summary(complaint_id: str) -> None:
    """
    Generate a 1–3 sentence digest for complaint_id and persist it.
    Also marks the customer's cif_summaries row as dirty.
    Non-fatal: logs and returns on any error.
    """
    try:
        supabase = get_supabase()
        settings = get_settings()

        result = (
            supabase.table("complaints")
            .select("masked_text, category, sentiment, severity, draft_response, route, current_tier, cif_id")
            .eq("complaint_id", complaint_id)
            .single()
            .execute()
        )
        if not result.data:
            logger.warning("[SUMMARY] complaint %s not found — skipping", complaint_id)
            return

        c = result.data
        cif_id = c.get("cif_id")

        route_label = {
            "AUTO": "auto-resolved",
            "HUMAN": "routed to human review",
            "ESCALATE": "escalated",
        }.get((c.get("route") or "").upper(), c.get("route") or "pending")

        user_msg = (
            f"Category: {c.get('category') or 'Unknown'}\n"
            f"Sentiment: {c.get('sentiment') or 'Unknown'}\n"
            f"Severity: {c.get('severity') or 'Unknown'}/5\n"
            f"Complaint text: {(c.get('masked_text') or '')[:800]}\n"
            f"AI draft response: {(c.get('draft_response') or 'None')[:400]}\n"
            f"Routing decision: {route_label}\n"
            f"Handling tier: {c.get('current_tier') or 1}"
        )

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=120,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()

        supabase.table("complaints").update(
            {"complaint_summary": summary}
        ).eq("complaint_id", complaint_id).execute()
        logger.info("[SUMMARY] wrote complaint_summary for %s", complaint_id)

        if cif_id:
            supabase.table("cif_summaries").upsert(
                {"cif_id": cif_id, "dirty": True},
                on_conflict="cif_id",
            ).execute()
            logger.info("[SUMMARY] marked cif_summaries dirty for cif=%s", cif_id)

    except Exception as exc:
        logger.error("[SUMMARY] generate_complaint_summary(%s) failed: %s", complaint_id, exc)
