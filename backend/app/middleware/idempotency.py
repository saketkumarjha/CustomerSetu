from fastapi import HTTPException, status
from app.db.supabase_client import get_supabase
import json


async def check_idempotency(idempotency_key: str) -> dict | None:
    """
    Check if this idempotency key has been seen before.

    Flow:
    1. Frontend generates a UUID per submission (X-Idempotency-Key header)
    2. On first request → key not found → process normally → store result
    3. On retry with same key → key found with cached response → return cached
    4. On retry while still processing → key found, no cache yet → return 202

    This prevents double-processing when frontend retries due to network error.

    Returns:
        None          → key is new, proceed normally
        dict          → cached response, return immediately
        "processing"  → still running, return 202
    """
    supabase = get_supabase()

    try:
        result = (
            supabase.table("idempotency_keys")
            .select("complaint_id, response_cache")
            .eq("key", idempotency_key)
            .execute()
        )
    except Exception:
        # If idempotency table query fails, allow request through
        # (fail open — better than blocking legitimate requests)
        return None

    if not result.data:
        return None  # new key — proceed

    record = result.data[0]

    if record.get("response_cache"):
        # Already processed — return cached response
        return record["response_cache"]

    # Key exists but no cached response yet — still processing
    raise HTTPException(
        status_code=status.HTTP_202_ACCEPTED,
        detail={
            "message": "Complaint is still being processed.",
            "complaint_id": record["complaint_id"],
            "status": "processing"
        }
    )


async def store_idempotency_key(
    idempotency_key: str,
    complaint_id: str
) -> None:
    """
    Store the idempotency key immediately when complaint is created.
    response_cache is NULL until pipeline completes.
    """
    supabase = get_supabase()
    try:
        supabase.table("idempotency_keys").insert({
            "key": idempotency_key,
            "complaint_id": complaint_id,
            "response_cache": None
        }).execute()
    except Exception as e:
        # Non-fatal — log and continue
        print(f"[IDEMPOTENCY] Failed to store key: {e}")


async def cache_idempotency_response(
    idempotency_key: str,
    response_data: dict
) -> None:
    """
    Cache the final pipeline response against the idempotency key.
    Called when pipeline completes successfully.
    """
    supabase = get_supabase()
    try:
        supabase.table("idempotency_keys").update({
            "response_cache": response_data
        }).eq("key", idempotency_key).execute()
    except Exception as e:
        print(f"[IDEMPOTENCY] Failed to cache response: {e}")