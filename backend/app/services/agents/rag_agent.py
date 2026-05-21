"""
Memory & RAG Agent — OpenAI Embeddings + pgvector Knowledge Base

Retrieves the top-3 most semantically similar past resolutions
from the knowledge_base table to provide context for the Resolution Agent.

Why RAG matters:
  Without RAG → Resolution Agent sees only the current complaint.
  With RAG    → Resolution Agent sees complaint + 3 proven past resolutions
                for similar issues. Response quality improves significantly.

Why same embedding model as duplicate detection:
  Consistency. Both use text-embedding-3-small with 512 dimensions.
  The vector space is shared — similar complaint texts cluster together
  regardless of whether we are checking duplicates or fetching context.
"""

import time
from openai import OpenAI
from app.core.config import get_settings
from app.db.supabase_client import get_supabase

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


async def retrieve_knowledge(
    masked_text: str,
    current_tier: int,
    complaint_id: str,
    branch_id: str = None,
    zone_id: str = None,
    region: str = None,
    n: int = 3
) -> dict:
    """
    Retrieve top-n most semantically similar resolutions from knowledge_base with tier-awareness.

    Args:
        masked_text: PII-masked complaint text
        category:    Complaint category from Classification Agent
        current_tier: Current tier level (e.g., branch, zone, etc.)
        tier_scope:  Specific scope within the tier (e.g., branch_id, zone_id)
        n:           Number of documents to retrieve (default 3)

    Returns dict with:
        documents:         List of retrieved resolution dicts
        retrieval_method:  "vector_search"
        total_in_kb:       Total documents in knowledge base
        tier_kb_coverage_score: Coverage score for the tier knowledge base
        missing_info_indicators: Indicators of missing context
        reasoning:         XAI reasoning string
    """

    settings = get_settings()
    client = _get_client()
    supabase = get_supabase()

    # Helper: Determine tier_scope string
    def determine_tier_scope(tier_level, branch_id, zone_id, region):
        if tier_level == 0:
            return None
        elif tier_level == 1 and branch_id:
            return f"BRANCH:{branch_id}"
        elif tier_level == 2 and zone_id:
            return f"ZONE:{zone_id}"
        elif tier_level == 3 and region:
            return f"REGION:{region}"
        elif tier_level == 4:
            return "HEAD_OFFICE"
        elif tier_level == 5:
            return "OMBUDSMAN"
        return None

    # Helper: Fetch previous KB IDs used (stub, replace with actual logic)
    def get_previous_kb_used(complaint_id):
        # TODO: Replace with actual fetch from escalation history
        return []

    # Generate embedding for the complaint text
    embed_response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=masked_text,
        dimensions=settings.openai_embedding_dimension,
    )
    embedding = embed_response.data[0].embedding

    previous_kb_ids = get_previous_kb_used(complaint_id)
    tier_scope = determine_tier_scope(current_tier, branch_id, zone_id, region)

    # Primary query: Tier-specific + scope-specific
    query = supabase.table("knowledge_base").select("id, resolution_text, tier_level, tier_scope, quality_score, embedding, verified").eq("tier_level", current_tier).eq("verified", True)
    if tier_scope is not None:
        query = query.or_(f"tier_scope.eq.{tier_scope},tier_scope.is.null")
    else:
        query = query.eq("tier_scope", None)
    if previous_kb_ids:
        query = query.not_.in_("id", previous_kb_ids)
    all_results = query.execute().data or []

    # Calculate similarity and sort
    def cosine_similarity(a, b):
        import numpy as np, json
        if isinstance(a, str):
            a = json.loads(a)
        if isinstance(b, str):
            b = json.loads(b)
        a, b = np.array(a, dtype=float), np.array(b, dtype=float)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom > 0 else 0.0

    for doc in all_results:
        doc["similarity"] = cosine_similarity(embedding, doc["embedding"])

    all_results.sort(key=lambda d: d["similarity"], reverse=True)
    results = all_results[:n]

    # Fallback if < n results: get general tier entries
    if len(results) < n:
        fallback_query = supabase.table("knowledge_base").select("id, resolution_text, tier_level, tier_scope, quality_score, embedding, verified").eq("tier_level", current_tier).eq("tier_scope", None).eq("verified", True)
        if previous_kb_ids:
            fallback_query = fallback_query.not_.in_("id", previous_kb_ids)
        fallback_results = fallback_query.execute().data or []
        for doc in fallback_results:
            doc["similarity"] = cosine_similarity(embedding, doc["embedding"])
        fallback_results.sort(key=lambda d: d["similarity"], reverse=True)
        results.extend(fallback_results[:n - len(results)])

    # Calculate coverage
    if results:
        avg_similarity = sum(d["similarity"] for d in results) / len(results)
        avg_quality = sum(d.get("quality_score", 0.5) for d in results) / len(results)
        tier_kb_coverage = avg_similarity * 0.6 + (len(results) / n) * 0.3 + avg_quality * 0.1
    else:
        tier_kb_coverage = 0.0

    # Format output
    rag_results = [
        {
            "id": d["id"],
            "text": d["resolution_text"],
            "similarity": d["similarity"],
            "tier_level": d["tier_level"],
            "tier_scope": d["tier_scope"],
            "quality_score": d.get("quality_score", 0.5)
        }
        for d in results
    ]

    return {
        "rag_results": rag_results,
        "tier_kb_coverage": tier_kb_coverage,
        "new_info_vs_previous": len(previous_kb_ids) > 0,
        "kb_entries_excluded": previous_kb_ids
    }


# ── Sync adapter used by graph.py (via asyncio.to_thread) ────────────────────

def retrieve_context(
    masked_text: str,
    category: str = "General Banking",
    n: int = 3,
) -> dict:
    """
    Synchronous wrapper called by the RAG node in the pipeline graph.

    Searches knowledge_base by category and semantic similarity, returning
    the top-n results with the key names graph.py expects.

    Returns:
        documents:         list of dicts with category, similarity, resolution_text, tier_level
        reasoning:         human-readable explanation of retrieval
        total_in_kb:       total verified entries in knowledge_base
        retrieval_method:  "vector_search"
    """
    settings = get_settings()
    client   = _get_client()
    supabase = get_supabase()

    import numpy as np
    import json

    def _cosine(a, b):
        if isinstance(a, str):
            a = json.loads(a)
        if isinstance(b, str):
            b = json.loads(b)
        a, b = np.array(a, dtype=float), np.array(b, dtype=float)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom > 0 else 0.0

    # Generate embedding for the complaint text
    embed_resp = client.embeddings.create(
        model      = settings.openai_embedding_model,
        input      = masked_text,
        dimensions = settings.openai_embedding_dimension,
    )
    query_embedding = embed_resp.data[0].embedding

    # Fetch verified entries — prefer matching category, fall back to all
    try:
        cat_rows = (
            supabase.table("knowledge_base")
            .select("id, category, resolution_text, tier_level, tier_scope, quality_score, embedding")
            .eq("verified", True)
            .eq("category", category)
            .execute()
            .data or []
        )
    except Exception:
        cat_rows = []

    # Fall back to general pool if category returns too few results
    if len(cat_rows) < n:
        try:
            all_rows = (
                supabase.table("knowledge_base")
                .select("id, category, resolution_text, tier_level, tier_scope, quality_score, embedding")
                .eq("verified", True)
                .execute()
                .data or []
            )
        except Exception:
            all_rows = []
        # Merge: category rows first, then others not already included
        seen_ids = {r["id"] for r in cat_rows}
        cat_rows = cat_rows + [r for r in all_rows if r["id"] not in seen_ids]

    total_in_kb = len(cat_rows)

    # Score and rank
    for row in cat_rows:
        emb = row.get("embedding")
        row["similarity"] = _cosine(query_embedding, emb) if emb else 0.0

    cat_rows.sort(key=lambda r: r["similarity"], reverse=True)
    top = cat_rows[:n]

    documents = [
        {
            "id":              r["id"],
            "category":        r.get("category", "General Banking"),
            "resolution_text": r.get("resolution_text", ""),
            "tier_level":      r.get("tier_level", 0),
            "tier_scope":      r.get("tier_scope"),
            "quality_score":   r.get("quality_score", 0.5),
            "similarity":      round(r["similarity"], 4),
        }
        for r in top
    ]

    if documents:
        avg_sim     = sum(d["similarity"] for d in documents) / len(documents)
        avg_quality = sum(d.get("quality_score", 0.5) for d in documents) / len(documents)
        tier_kb_coverage_score = (
            avg_sim * 0.6
            + (len(documents) / n) * 0.3
            + avg_quality * 0.1
        )
        reasoning = (
            f"Retrieved {len(documents)} document(s) from {total_in_kb} verified KB entries. "
            f"Category filter: '{category}'. "
            f"Average similarity: {avg_sim:.1%}. "
            f"Top match similarity: {documents[0]['similarity']:.1%}. "
            f"KB coverage score: {tier_kb_coverage_score:.2f}."
        )
    else:
        tier_kb_coverage_score = 0.0
        reasoning = (
            f"No matching documents found in knowledge base "
            f"({total_in_kb} verified entries searched, category='{category}'). "
            f"Resolution Agent will rely on LLM general knowledge only."
        )

    return {
        "documents":             documents,
        "reasoning":             reasoning,
        "total_in_kb":           total_in_kb,
        "retrieval_method":      "vector_search",
        "tier_kb_coverage_score": round(tier_kb_coverage_score, 4),
    }