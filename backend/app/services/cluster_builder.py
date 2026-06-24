"""
Cluster Builder (v2)
====================
Aggregates `complaint_signals` rows into `complaint_clusters` snapshots.
Grouping key: (event_type, product, region) — channel is now a diversity feature.
Adds: distinct_customers, velocity_ratio, channel_diversity, urgency aggregates,
      min_complaints_met evidence gate. All model-input features are non-null.
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Any

from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

_LOOKBACK_HOURS = 25
_NEGATIVE_SENTIMENTS = {"negative", "frustrated", "angry", "dissatisfied"}
_MIN_COMPLAINTS_TO_SCORE = 2
_DEFAULT_SEVERITY = 2


def _make_cluster_id(event_type: str, product: str, region: str) -> str:
    key = f"{event_type or ''}|{product or ''}|{region or ''}"
    digest = hashlib.md5(key.encode()).hexdigest()[:8].upper()
    return f"CL-{digest}"


def _floor_to_5min(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0, minute=(dt.minute // 5) * 5)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def build_clusters() -> None:
    supabase = get_supabase()
    now_utc  = datetime.now(timezone.utc)
    cutoff   = now_utc - timedelta(hours=_LOOKBACK_HOURS)
    snapshot = _floor_to_5min(now_utc)

    logger.info("[CLUSTERS] build_clusters() started — snapshot_time=%s", snapshot.isoformat())

    try:
        result = (
            supabase.table("complaint_signals")
            .select(
                "complaint_id, customer_id, event_type, product, region, channel, "
                "severity, urgency_score, sentiment, financial_loss_flag, "
                "rbi_reportable, is_duplicate, created_at"
            )
            .gte("created_at", cutoff.isoformat())
            .execute()
        )
    except Exception:
        logger.exception("[CLUSTERS] Failed to fetch complaint_signals")
        return

    signals: list[dict[str, Any]] = result.data or []
    if not signals:
        logger.info("[CLUSTERS] No signals in last %dh", _LOOKBACK_HOURS)
        return

    logger.info("[CLUSTERS] Fetched %d signals", len(signals))

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for s in signals:
        key = (
            s.get("event_type") or "unknown",
            s.get("product")    or "unknown",
            s.get("region")     or "unknown",
        )
        groups[key].append(s)

    snapshots: list[dict[str, Any]] = []
    cutoff_1h  = now_utc - timedelta(hours=1)
    cutoff_6h  = now_utc - timedelta(hours=6)
    cutoff_24h = now_utc - timedelta(hours=24)

    for (event_type, product, region), group_signals in groups.items():
        for s in group_signals:
            s["_ts"] = _parse_ts(s.get("created_at"))
        windowed = [s for s in group_signals if s["_ts"] is not None]

        sig_1h  = [s for s in windowed if s["_ts"] >= cutoff_1h]
        sig_6h  = [s for s in windowed if s["_ts"] >= cutoff_6h]
        sig_24h = [s for s in windowed if s["_ts"] >= cutoff_24h]

        count_1h, count_6h, count_24h = len(sig_1h), len(sig_6h), len(sig_24h)
        total = len(group_signals)

        def _distinct_customers(sigs):
            return len({s.get("customer_id") for s in sigs if s.get("customer_id")})
        dc_1h  = _distinct_customers(sig_1h)
        dc_6h  = _distinct_customers(sig_6h)
        dc_24h = _distinct_customers(sig_24h)

        rate_6h_per_hr = count_6h / 6.0
        velocity_ratio = round(count_1h / rate_6h_per_hr, 4) if rate_6h_per_hr > 0 else 0.0

        channel_diversity = len({(s.get("channel") or "unknown") for s in sig_24h}) or 1

        severities = [s["severity"] for s in group_signals if s.get("severity") is not None]
        avg_severity = round(sum(severities) / len(severities), 2) if severities else _DEFAULT_SEVERITY
        max_severity = max(severities) if severities else _DEFAULT_SEVERITY

        urgencies = [s["urgency_score"] for s in group_signals if s.get("urgency_score") is not None]
        avg_urgency = round(sum(urgencies) / len(urgencies), 2) if urgencies else 0.0
        max_urgency = max(urgencies) if urgencies else 0.0

        neg = sum(1 for s in group_signals if (s.get("sentiment") or "").lower() in _NEGATIVE_SENTIMENTS)
        fin = sum(1 for s in group_signals if s.get("financial_loss_flag"))
        rbi = sum(1 for s in group_signals if s.get("rbi_reportable"))
        dup = sum(1 for s in group_signals if s.get("is_duplicate"))

        timestamps = [s["_ts"] for s in windowed]
        cluster_id = _make_cluster_id(event_type, product, region)

        snapshots.append({
            "cluster_id":                 cluster_id,
            "snapshot_time":              snapshot.isoformat(),
            "event_type":                 event_type,
            "product":                    product,
            "region":                     region,
            "complaints_1h":              count_1h,
            "complaints_6h":              count_6h,
            "complaints_24h":             count_24h,
            "distinct_customers_1h":      dc_1h,
            "distinct_customers_6h":      dc_6h,
            "distinct_customers_24h":     dc_24h,
            "velocity_ratio":             velocity_ratio,
            "channel_diversity":          channel_diversity,
            "first_seen_at":              min(timestamps).isoformat() if timestamps else None,
            "last_seen_at":               max(timestamps).isoformat() if timestamps else None,
            "avg_severity":               avg_severity,
            "max_severity":               max_severity,
            "avg_urgency":                avg_urgency,
            "max_urgency":                max_urgency,
            "negative_sentiment_ratio":   _safe_ratio(neg, total),
            "financial_loss_ratio":       _safe_ratio(fin, total),
            "rbi_reportable_ratio":       _safe_ratio(rbi, total),
            "duplicate_ratio":            _safe_ratio(dup, total),
            "min_complaints_met":         count_24h >= _MIN_COMPLAINTS_TO_SCORE,
            "risk_score":                 None,
            "growth_probability":         None,
            "alert_priority":             None,
            "predicted_impact_customers": None,
            "confidence_score":           None,
            "status":                     "active",
            "confirmed_incident":         None,
            "resolved_at":                None,
        })

    if not snapshots:
        logger.info("[CLUSTERS] No snapshots to write")
        return

    try:
        result = (
            supabase.table("complaint_clusters")
            .upsert(snapshots, on_conflict="cluster_id,snapshot_time")
            .execute()
        )
        logger.info("[CLUSTERS] Upserted %d snapshots", len(result.data or []))
    except Exception:
        logger.exception("[CLUSTERS] Failed to upsert cluster snapshots")


async def score_pending_clusters() -> None:
    """
    Score all active cluster snapshots that have hit the evidence gate
    (min_complaints_met=True) but haven't been scored yet (risk_score IS NULL).

    Called by the scheduler every 5 minutes, right after build_clusters().
    Can also be called manually for backfill.
    """
    from app.services.incident_scorer import score_cluster, _MODEL_LOADED

    if not _MODEL_LOADED:
        logger.warning("[SCORER] Model not loaded — skipping score_pending_clusters()")
        return

    supabase = get_supabase()

    try:
        rows = (
            supabase.table("complaint_clusters")
            .select("*")
            .eq("min_complaints_met", True)
            .is_("risk_score", "null")
            .execute()
        ).data or []
    except Exception:
        logger.exception("[SCORER] Failed to fetch unscored clusters")
        return

    if not rows:
        logger.info("[SCORER] No unscored clusters found")
        return

    logger.info("[SCORER] Scoring %d cluster snapshots", len(rows))
    scored_count = 0

    for snap in rows:
        result = score_cluster(snap)
        if not result["scored"]:
            logger.debug(
                "[SCORER] Skipped cluster_id=%s reason=%s",
                snap.get("cluster_id"), result.get("reason"),
            )
            continue

        try:
            supabase.table("complaint_clusters").update({
                "risk_score":                 result["risk_score"],
                "growth_probability":         result["growth_probability"],
                "alert_priority":             result["alert_priority"],
                "confidence_score":           result["confidence_score"],
                "predicted_impact_customers": result["predicted_impact_customers"],
            }).eq("cluster_id", snap["cluster_id"]).eq(
                "snapshot_time", snap["snapshot_time"]
            ).execute()
            scored_count += 1
            logger.info(
                "[SCORER] Scored cluster_id=%s risk_score=%s priority=%s departments=%s",
                snap.get("cluster_id"),
                result["risk_score"],
                result["alert_priority"],
                result.get("departments"),
            )
        except Exception:
            logger.exception(
                "[SCORER] Failed to write score for cluster_id=%s", snap.get("cluster_id")
            )

    logger.info("[SCORER] score_pending_clusters() done — %d scored", scored_count)