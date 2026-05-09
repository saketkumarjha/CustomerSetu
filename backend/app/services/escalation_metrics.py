"""
Escalation Metrics Tracker

Writes lightweight event records for aggregation.
All writes are best-effort — metrics failures never block the pipeline.

Table required: escalation_events
  id            BIGSERIAL PRIMARY KEY
  complaint_id  TEXT NOT NULL
  event_type    VARCHAR(50) NOT NULL
  metadata      JSONB
  created_at    TIMESTAMPTZ DEFAULT NOW()
"""

from datetime import datetime, timezone
from app.db.supabase_client import get_supabase


def track_escalation_event(
    complaint_id: str,
    event_type: str,
    metadata: dict = None,
) -> None:
    """
    event_type values:
      ESCALATION_STARTED   — orchestrator entered for the first time
      ESCALATION_RESOLVED  — ended with auto_respond
      ESCALATION_FAILED    — partial pipeline raised an exception
      MAX_TIER_REACHED     — hit Tier 5 with confidence still < 95%
      MAX_ITERATIONS       — hit 5 re-runs
      LOOP_DETECTED        — circular or rapid-fire path detected
    """
    try:
        supabase = get_supabase()
        supabase.table("escalation_events").insert({
            "complaint_id": complaint_id,
            "event_type": event_type,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass
