"""
In-memory cache to prevent rapid-fire re-analysis immediately after escalating to a new tier.

When a complaint is escalated to Tier N, Agent 10.5 should not re-analyze escalation
at Tier N for a short window — give the tier a chance to resolve first.
TTL default: 30 seconds (from config: escalation_cache_ttl_seconds).
"""

import time
from threading import Lock

_cache: dict[str, float] = {}
_lock = Lock()


def mark_just_escalated(complaint_id: str, to_tier: int) -> None:
    key = f"{complaint_id}::{to_tier}"
    with _lock:
        _cache[key] = time.time()


def should_skip_escalation_check(
    complaint_id: str,
    current_tier: int,
    ttl_seconds: int = 30,
) -> bool:
    key = f"{complaint_id}::{current_tier}"
    with _lock:
        ts = _cache.get(key)
        if ts is None:
            return False
        if time.time() - ts < ttl_seconds:
            return True
        del _cache[key]
        return False


def clear_complaint_cache(complaint_id: str) -> None:
    with _lock:
        stale = [k for k in _cache if k.startswith(f"{complaint_id}::")]
        for k in stale:
            del _cache[k]
