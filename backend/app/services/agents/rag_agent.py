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


def retrieve_context(masked_text: str, category: str, n: int = 3) -> dict:
    """
    Retrieve top-n most semantically similar resolutions from knowledge_base.

    Args:
        masked_text: PII-masked complaint text
        category:    Complaint category from Classification Agent
                     Used to build XAI context about what was retrieved
        n:           Number of documents to retrieve (default 3)

    Returns dict with:
        documents:         List of retrieved resolution dicts
        retrieval_method:  "vector_search"
        total_in_kb:       Total documents in knowledge base
        reasoning:         XAI reasoning string
    """
    settings = get_settings()
    client = _get_client()
    supabase = get_supabase()

    # Generate embedding for the complaint text
    embed_response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=masked_text,
        dimensions=settings.openai_embedding_dimension,
    )
    embedding = embed_response.data[0].embedding

    # Count total knowledge base documents for XAI context
    count_result = (
        supabase.table("knowledge_base")
        .select("id", count="exact")
        .execute()
    )
    total_in_kb = count_result.count or 0

    if total_in_kb == 0:
        return {
            "documents": [],
            "retrieval_method": "vector_search",
            "total_in_kb": 0,
            "reasoning": (
                "Knowledge base is empty. No context retrieved.\n"
                "Resolution Agent will generate response from scratch.\n"
                "Add resolved complaints to knowledge_base to improve future responses."
            ),
        }

    # Query pgvector match function
    result = supabase.rpc(
        "match_knowledge_base",
        {
            "query_embedding": embedding,
            "match_count": n,
        },
    ).execute()

    documents = result.data or []

    if not documents:
        reasoning = (
            f"Knowledge base contains {total_in_kb} documents.\n"
            f"No sufficiently similar resolutions found for category: {category}.\n"
            f"Resolution Agent will generate response from training knowledge only."
        )
    else:
        doc_lines = []
        for i, doc in enumerate(documents, 1):
            similarity = doc.get("similarity", 0)
            doc_category = doc.get("category", "Unknown")
            doc_lines.append(
                f"  {i}. [{doc_category}] similarity: {similarity:.1%} "
                f"(quality: {doc.get('quality_score', 0.5):.1f})"
            )

        reasoning = (
            f"Retrieved {len(documents)} context document(s) from "
            f"knowledge base ({total_in_kb} total).\n"
            f"Matches found:\n" + "\n".join(doc_lines) + "\n"
            f"These resolutions will guide the Resolution Agent's draft.\n"
            f"Higher similarity + higher quality = stronger guidance."
        )

    return {
        "documents": documents,
        "retrieval_method": "vector_search",
        "total_in_kb": total_in_kb,
        "reasoning": reasoning,
    }