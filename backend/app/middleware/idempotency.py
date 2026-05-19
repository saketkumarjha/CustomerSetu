from fastapi import status
from fastapi.responses import JSONResponse
from app.db.supabase_client import get_supabase
import json


async def check_idempotency(idempotency_key: str) -> dict | JSONResponse | None:
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

    # Key exists but no cached response yet — still processing.
    # Return a JSONResponse directly: 202 is a success code, not an error,
    # so raising HTTPException (which always formats as {"detail": ...}) is wrong.
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": "Complaint is still being processed.",
            "complaint_id": record["complaint_id"],
            "status": "processing",
        },
    )


async def store_idempotency_key(
    idempotency_key: str,
    complaint_id: str
) -> bool:
    """
    Store the idempotency key immediately when complaint is created.
    response_cache is NULL until pipeline completes.

    Uses upsert (on_conflict=ignore) so that a simultaneous duplicate request
    that races past check_idempotency() does not create a second complaint row.
    The second caller hits the DB unique constraint, this insert is ignored,
    and the complaint_id written by the first caller is preserved.

    Returns True if this was the first writer, False if the key already existed.

    NOTE: requires a UNIQUE constraint on idempotency_keys.key in the DB schema.
    Run this migration if not already present:
        ALTER TABLE idempotency_keys ADD CONSTRAINT idempotency_keys_key_unique UNIQUE (key);
    """
    supabase = get_supabase()
    try:
        result = (
            supabase.table("idempotency_keys")
            .upsert(
                {"key": idempotency_key, "complaint_id": complaint_id, "response_cache": None},
                on_conflict="key",
                ignore_duplicates=True,
            )
            .execute()
        )
        # If data is empty the row already existed (duplicate was ignored)
        return bool(result.data)
    except Exception as e:
        print(f"[IDEMPOTENCY] Failed to store key: {e}")
        return True  # assume first writer — do not block the complaint


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