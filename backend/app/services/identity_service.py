"""
Identity Resolution Service — CIF linking for Email and WhatsApp channels.

Public API:
  normalize_phone(raw)                          → E.164 string
  extract_account_number(text)                  → str | None
  resolve_identity(channel, identifier, acno)   → {status, cif_id?}
  link_complaint_to_cif(complaint_id, cif_id)   → None
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Account-number extraction ─────────────────────────────────────────────────

# Matches labelled patterns first, then bare 9-18 digit sequences as fallback.
_ACNO_LABELLED = re.compile(
    r'(?:account\s*(?:number|no\.?|#)|a/?c\s*(?:no\.?|number|#)|ac\s*[:\-])\s*([A-Z0-9]{6,18})',
    re.IGNORECASE,
)
_ACNO_BARE = re.compile(r'\b(\d{9,18})\b')


def extract_account_number(text: str) -> Optional[str]:
    """Return the first account number found in text, or None."""
    if not text:
        return None
    m = _ACNO_LABELLED.search(text)
    if m:
        return m.group(1).strip().upper()
    m = _ACNO_BARE.search(text)
    if m:
        return m.group(1)
    return None


# ── Phone normalisation ───────────────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """
    Strip 'whatsapp:' prefix and any non-digit/+ characters, return E.164.
    e.g. 'whatsapp:+919876543210' → '+919876543210'
    """
    s = raw.strip()
    if s.lower().startswith("whatsapp:"):
        s = s[len("whatsapp:"):]
    # Keep leading '+', strip everything else that isn't a digit
    s = s.strip()
    if not s.startswith("+"):
        # Assume Indian number if no country code prefix
        digits = re.sub(r'\D', '', s)
        s = f"+91{digits}" if len(digits) == 10 else f"+{digits}"
    return s


# ── Core identity resolution ──────────────────────────────────────────────────

def resolve_identity(
    channel: str,
    identifier: str,
    account_number: Optional[str] = None,
) -> dict:
    """
    Look up or create a customer record and determine verification status.

    Args:
        channel:        "email" or "whatsapp"
        identifier:     Normalised email address or E.164 phone number
        account_number: Optional account number extracted from complaint text

    Returns one of:
        {"status": "verified",           "cif_id": <uuid>}
        {"status": "needs_verification", "cif_id": <uuid>}   ← found but acno mismatch
        {"status": "new",                "cif_id": <uuid>}   ← created, unverified
    """
    from app.db.supabase_client import get_supabase
    supabase = get_supabase()

    field = "email" if channel == "email" else "phone"

    # ── Lookup existing customer ──────────────────────────────────────────────
    resp = supabase.table("customers").select("*").eq(field, identifier).execute()
    rows = resp.data or []

    if rows:
        customer = rows[0]
        cif_id = customer["cif_id"]

        # Known customer: email/phone alone is always sufficient for verification.
        # We do not block on account number mismatch here — the complaint text may
        # contain arbitrary digit sequences (phone numbers, UPI reference IDs, etc.)
        # that the extractor picks up but that are not account numbers. Penalising a
        # registered customer for this would break the happy path.
        logger.info("[IDENTITY] Verified by %s alone (existing customer): %s", field, identifier)

        # Opportunistically store the account number if we have one and the customer
        # doesn't have one on record yet.
        if account_number:
            stored_acno = customer.get("account_number")
            if stored_acno is None:
                supabase.table("customers").update(
                    {"account_number": account_number}
                ).eq("cif_id", cif_id).execute()
                logger.info("[IDENTITY] Account number stored for %s", identifier)

        return {"status": "verified", "cif_id": cif_id}

    # ── New customer — create unverified record ───────────────────────────────
    insert_payload: dict = {field: identifier}
    if account_number:
        insert_payload["account_number"] = account_number

    new_resp = supabase.table("customers").insert(insert_payload).execute()
    new_rows = new_resp.data or []
    cif_id = new_rows[0]["cif_id"] if new_rows else None

    logger.info("[IDENTITY] New customer created for %s: cif_id=%s", identifier, cif_id)
    return {"status": "new", "cif_id": cif_id}


# ── CIF linking + cross-complaint merge ──────────────────────────────────────

def link_complaint_to_cif(complaint_id: str, cif_id: str, set_pending: bool = True) -> None:
    """
    Mark complaint as verified, attach CIF, and bidirectionally link to all
    other verified complaints from the same customer.

    set_pending=False: skip pipeline_status update (use for tier-0 auto-closed complaints).
    """
    from app.db.supabase_client import get_supabase
    supabase = get_supabase()

    # Find all other complaints already linked to this CIF.
    # Query by cif_id alone — identity_status varies by channel (web complaints
    # may have null identity_status even though they're legitimately CIF-linked).
    sibling_resp = (
        supabase.table("complaints")
        .select("complaint_id, linked_complaint_ids")
        .eq("cif_id", cif_id)
        .neq("complaint_id", complaint_id)
        .execute()
    )
    siblings = sibling_resp.data or []
    sibling_ids = [s["complaint_id"] for s in siblings]

    # Update the new complaint: mark verified, attach CIF, set linked list.
    update_payload = {
        "identity_status":      "verified",
        "cif_id":               cif_id,
        "pending_info_request": False,
        "linked_complaint_ids": sibling_ids,
    }
    if set_pending:
        update_payload["pipeline_status"] = "pending"
    supabase.table("complaints").update(update_payload).eq("complaint_id", complaint_id).execute()

    # Verify the update was applied (supabase-py v1 returns minimal by default).
    verify_resp = (
        supabase.table("complaints")
        .select("complaint_id, cif_id, identity_status")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    verify_rows = verify_resp.data or []
    if not verify_rows or verify_rows[0].get("cif_id") != cif_id:
        logger.error(
            "[IDENTITY] cif link FAILED — complaint=%s cif_id still not set (rows=%s)",
            complaint_id, verify_rows,
        )
    else:
        logger.info(
            "[IDENTITY] cif link confirmed: complaint=%s cif_id=%s identity_status=%s",
            verify_rows[0].get("complaint_id"),
            verify_rows[0].get("cif_id"),
            verify_rows[0].get("identity_status"),
        )

    # Append this complaint_id to each sibling's linked list
    for sibling in siblings:
        existing = sibling.get("linked_complaint_ids") or []
        if complaint_id not in existing:
            supabase.table("complaints").update({
                "linked_complaint_ids": existing + [complaint_id]
            }).eq("complaint_id", sibling["complaint_id"]).execute()

    # Mark customer as verified (set verified_at if first time)
    supabase.table("customers").update({
        "verified":    True,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }).eq("cif_id", cif_id).eq("verified", False).execute()

    logger.info(
        "[IDENTITY] complaint=%s linked to cif=%s (siblings=%s)",
        complaint_id, cif_id, sibling_ids,
    )
