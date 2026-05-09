"""
Contact Info Service

Fetches tier-specific contact details for injection into auto-responses.

Production flow:
  Tier 1 → SELECT from branches WHERE branch_id = complaint.branch_id
  Tier 2 → SELECT from zones    WHERE zone_id   = complaint.zone_id
  Tier 3 → SELECT from regions  WHERE region_id = complaint.region_id
  Tier 4 → SELECT from tier_config WHERE tier_level = 4

Prototype: returns static mock data.  Replace _fetch_from_db() calls when
the branches/zones/regions tables are available in Supabase.
"""
from typing import Optional

from app.db.supabase_client import get_supabase

# ── Default contact data per tier ────────────────────────────────────────────
# Mirrors what the tier_config + branches/zones tables would return.
_TIER_DEFAULTS: dict[int, dict] = {
    1: {
        "tier_name": "Branch Level",
        "phone":     "1800-22-2244",
        "email":     "branch.support@unionbankofindia.com",
        "hours":     "Mon–Sat  9:00 AM – 5:00 PM",
        "address":   "Your nearest Union Bank of India Branch",
    },
    2: {
        "tier_name": "Zonal Office",
        "phone":     "1800-22-2255",
        "email":     "zonal.grievance@unionbankofindia.com",
        "hours":     "Mon–Fri  9:00 AM – 5:30 PM",
        "address":   "Union Bank of India Zonal Office",
    },
    3: {
        "tier_name": "Regional Office",
        "phone":     "1800-22-2266",
        "email":     "regional.grievance@unionbankofindia.com",
        "hours":     "Mon–Fri  9:00 AM – 5:30 PM",
        "address":   "Union Bank of India Regional Office",
    },
    4: {
        "tier_name": "Head Office / Nodal Officer",
        "phone":     "1800-22-2277",
        "email":     "nodal.officer@unionbankofindia.com",
        "hours":     "Mon–Fri  9:00 AM – 5:30 PM",
        "address":   "Union Bank of India, Head Office, Mumbai – 400 021",
    },
}


def get_tier_contacts(tier_level: int, scope_id: Optional[str] = None) -> dict:
    """
    Return contact details for a given tier.

    Args:
        tier_level: 1–4 (clamped automatically).
        scope_id:   Branch/zone/region ID for specific lookups (Tier 1–3 only).
                    When provided, attempts a DB lookup before falling back to defaults.

    Returns dict:
        tier_level, name, address, phone, email, hours
    """
    tier_level = max(1, min(tier_level, 4))
    info = _TIER_DEFAULTS[tier_level].copy()

    if scope_id:
        db_info = _fetch_from_db(tier_level, scope_id)
        if db_info:
            info.update(db_info)

    return {
        "tier_level": tier_level,
        "name":       info["tier_name"],
        "address":    info["address"],
        "phone":      info["phone"],
        "email":      info["email"],
        "hours":      info["hours"],
    }


def _fetch_from_db(tier_level: int, scope_id: str) -> Optional[dict]:
    """
    Attempt to fetch actual contact data from Supabase.

    Table mapping:
      tier 1 → branches (branch_id)
      tier 2 → zones    (zone_id)
      tier 3 → regions  (region_id)
      tier 4 → tier_config (tier_level)

    Returns None if the table doesn't exist or the row isn't found
    (prototype: these tables may not be seeded yet).
    """
    supabase = get_supabase()
    try:
        table_map = {1: ("branches", "branch_id"), 2: ("zones", "zone_id"), 3: ("regions", "region_id")}
        if tier_level in table_map:
            table, pk = table_map[tier_level]
            result = (
                supabase.table(table)
                .select("name,address,phone,email,hours")
                .eq(pk, scope_id)
                .limit(1)
                .execute()
            )
            if result.data:
                row = result.data[0]
                return {
                    "tier_name": row.get("name", _TIER_DEFAULTS[tier_level]["tier_name"]),
                    "address":   row.get("address", _TIER_DEFAULTS[tier_level]["address"]),
                    "phone":     row.get("phone",   _TIER_DEFAULTS[tier_level]["phone"]),
                    "email":     row.get("email",   _TIER_DEFAULTS[tier_level]["email"]),
                    "hours":     row.get("hours",   _TIER_DEFAULTS[tier_level]["hours"]),
                }
    except Exception:
        pass  # Table doesn't exist yet — fall through to defaults
    return None
