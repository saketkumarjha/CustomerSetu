"""
Duplicate Detection Agent — OpenAI Embeddings + pgvector

Strategy:
1. Generate 512-dim embedding from masked_text using text-embedding-3-small
2. Run cosine similarity search against all existing complaints in Supabase
3. If similarity > threshold (0.92) → DUPLICATE → Supervisor exits pipeline early
4. If unique → store embedding on complaint record for future comparisons

Why masked_text for embeddings (not original_text):
  Two customers reporting the same issue will use different names and
  reference numbers. After PII masking, both texts become semantically
  identical — "My <PERSON> account had <IN_AADHAAR> debited without consent"
  This dramatically improves duplicate detection accuracy.

Why embedding before LLM agents:
  Duplicate detection costs ~$0.00002 per call (embedding only).
  Classification + Sentiment + RAG + Resolution costs ~$0.05 per run.
  Catching duplicates here saves 99.9% of LLM spend on repeat submissions.
"""

from openai import OpenAI
from app.core.config import get_settings
from app.db.supabase_client import get_supabase

# Module-level singleton — avoids re-initialising client per request
_openai_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def generate_embedding(text: str) -> list[float]:
    """
    Generate a 512-dimensional embedding using OpenAI text-embedding-3-small.

    Why 512 dimensions (not the default 1536):
      text-embedding-3-small supports Matryoshka Representation Learning —
      you can truncate to any dimension without retraining. 512 gives
      95% of the accuracy at 1/3 the storage cost. Matches our pgvector
      column definition (VECTOR(512)).

    Args:
        text: The masked complaint text

    Returns:
        List of 512 floats representing the semantic meaning of the text
    """
    settings = get_settings()
    client = _get_client()

    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        dimensions=settings.openai_embedding_dimension,
    )
    return response.data[0].embedding


def check_for_duplicate(
    complaint_id: str,
    masked_text: str,
    threshold: float = 0.92,
) -> dict:
    """
    Full duplicate detection pipeline.

    Steps:
    1. Generate embedding for masked_text
    2. Query pgvector match_complaints function
    3. Exclude self-comparison (same complaint_id)
    4. Return result with embedding for storage

    Args:
        complaint_id: Current complaint's ID (excluded from search)
        masked_text:  PII-masked complaint text from PII agent
        threshold:    Cosine similarity threshold (default 0.92)

    Returns dict with:
        is_duplicate:      bool
        duplicate_of:      complaint_id of match (if duplicate)
        similarity_score:  float 0.0-1.0
        embedding:         the generated embedding (for storage)
        total_searched:    how many complaints were compared
        reasoning:         XAI reasoning string
    """
    supabase = get_supabase()
    embedding = generate_embedding(masked_text)

    # Query pgvector match function
    # Returns complaints ordered by cosine similarity, above threshold
    result = supabase.rpc(
        "match_complaints",
        {
            "query_embedding": embedding,
            "match_threshold": threshold,
            "match_count": 3,  # get top 3, exclude self
        },
    ).execute()

    # Count total complaints for XAI context
    total_count_result = (
        supabase.table("complaints")
        .select("complaint_id", count="exact")
        .execute()
    )
    total_searched = total_count_result.count or 0

    matches = result.data or []

    # Filter out self-comparison
    matches = [m for m in matches if m["complaint_id"] != complaint_id]

    if matches:
        best_match = matches[0]
        similarity = round(best_match["similarity"], 4)

        reasoning = (
            f"DUPLICATE DETECTED.\n"
            f"Semantic similarity search across {total_searched} existing complaints.\n"
            f"Best match: {best_match['complaint_id']} "
            f"(similarity: {similarity:.1%}).\n"
            f"Threshold: {threshold:.0%}. Result: {similarity:.1%} > {threshold:.0%}.\n"
            f"Action: Merging to existing ticket. "
            f"No LLM processing required — saving API cost.\n"
            f"Embedding model: text-embedding-3-small (512 dimensions)."
        )

        return {
            "is_duplicate": True,
            "duplicate_of": best_match["complaint_id"],
            "similarity_score": similarity,
            "embedding": embedding,
            "total_searched": total_searched,
            "reasoning": reasoning,
            "all_matches": [
                {
                    "complaint_id": m["complaint_id"],
                    "similarity": round(m["similarity"], 4),
                }
                for m in matches[:3]
            ],
        }

    # No duplicate found — return embedding for storage
    reasoning = (
        f"UNIQUE complaint confirmed.\n"
        f"Semantic similarity search across {total_searched} existing complaints.\n"
        f"No match found above {threshold:.0%} threshold.\n"
        f"Closest match (if any): below {threshold:.0%} similarity.\n"
        f"Embedding stored for future duplicate detection.\n"
        f"Embedding model: text-embedding-3-small (512 dimensions).\n"
        f"Proceeding to full AI pipeline analysis."
    )

    return {
        "is_duplicate": False,
        "duplicate_of": None,
        "similarity_score": 0.0,
        "embedding": embedding,
        "total_searched": total_searched,
        "reasoning": reasoning,
        "all_matches": [],
    }


def store_embedding(complaint_id: str, embedding: list[float]) -> None:
    """
    Store the complaint's embedding in Supabase for future duplicate searches.
    Called after confirming complaint is unique.
    """
    supabase = get_supabase()
    try:
        supabase.table("complaints").update(
            {"embedding": embedding}
        ).eq("complaint_id", complaint_id).execute()
    except Exception as e:
        # Non-fatal — log and continue
        print(f"[DUPLICATE] Failed to store embedding: {e}")