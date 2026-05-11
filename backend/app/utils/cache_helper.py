from datetime import datetime, timedelta

_cache: dict = {}


def cached_team_metrics(tier_level: int, ttl_minutes: int = 5):
    cache_key = f"team_metrics_{tier_level}"
    now = datetime.utcnow()

    if cache_key in _cache:
        cached_data, cached_time = _cache[cache_key]
        if now - cached_time < timedelta(minutes=ttl_minutes):
            return cached_data

    from app.services.dashboard_aggregator import get_team_metrics
    fresh_data = get_team_metrics(tier_level)
    _cache[cache_key] = (fresh_data, now)
    return fresh_data
