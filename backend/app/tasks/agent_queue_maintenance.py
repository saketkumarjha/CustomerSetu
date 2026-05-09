"""
Agent Queue Maintenance — Background scheduled tasks.

Three tasks:
  Task 1: queue_rebalancer     — every 5 minutes
  Task 2: sla_monitor          — every 1 minute
  Task 3: agent_workload_balancer — every 10 minutes

Use APScheduler or Celery Beat to schedule these in production.
For development, call each function manually or wire into a startup event.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.db.supabase_client import get_supabase
from app.services.queue_service import rebalance_queue
from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def queue_rebalancer() -> None:
    """
    Every 5 minutes:
      - Check for overdue complaints in each tier's queue
      - Boost priority when SLA is approaching
      - Reassign complaints whose agent went offline
    """
    settings = get_settings()
    tier_levels = list(settings.tier_agent_mapping.keys())

    for tier in tier_levels:
        try:
            summary = rebalance_queue(tier)
            logger.info(
                "[QueueMaintenance] rebalance tier=%s reassigned=%s boosted=%s",
                tier, summary["reassigned"], summary["priority_boosted"],
            )
        except Exception as exc:
            logger.error("[QueueMaintenance] rebalance error tier=%s: %s", tier, exc)


async def sla_monitor() -> None:
    """
    Every 1 minute:
      - Find complaints in queue whose SLA deadline is within 1 hour
      - Notify the assigned agent (simulated via print; wire email/Slack in prod)
      - If SLA has already breached, transition status → overdue_review
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    one_hour_later = now + timedelta(hours=1)

    result = (
        supabase.table("agent_queue")
        .select("complaint_id, assigned_to, sla_deadline, tier_level, status")
        .in_("status", ["QUEUED", "ASSIGNED", "IN_REVIEW"])
        .not_.is_("sla_deadline", "null")
        .execute()
    )

    for row in result.data or []:
        sla_str = row.get("sla_deadline")
        if not sla_str:
            continue

        try:
            sla_dt = datetime.fromisoformat(sla_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        complaint_id = row["complaint_id"]
        assigned_to  = row.get("assigned_to")

        if sla_dt < now:
            # SLA already breached
            try:
                supabase.table("complaints").update({
                    "status": "overdue_review",
                }).eq("complaint_id", complaint_id).eq("status", "pending_review").execute()
                logger.warning("[SLAMonitor] SLA BREACHED complaint=%s", complaint_id)
            except Exception as exc:
                logger.error("[SLAMonitor] breach update failed complaint=%s: %s", complaint_id, exc)

        elif sla_dt <= one_hour_later and assigned_to:
            # Approaching breach — notify agent
            logger.warning(
                "[SLAMonitor] SLA approaching complaint=%s agent=%s deadline=%s",
                complaint_id, assigned_to, sla_str,
            )
            _notify_agent_sla_risk(assigned_to, complaint_id, sla_str)


async def agent_workload_balancer() -> None:
    """
    Every 10 minutes:
      - Check if any agent is over max_workload
      - Redistribute excess items to under-loaded agents in the same tier
    """
    from app.services.agent_assignment_service import find_best_agent, get_agent_workload
    settings = get_settings()
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    max_load = settings.agent_max_workload

    for tier, agents in settings.tier_agent_mapping.items():
        for agent_id in agents:
            load = get_agent_workload(agent_id)
            if load <= max_load:
                continue

            # Find overflow complaints (ASSIGNED but not IN_REVIEW) for this agent
            overflow = (
                supabase.table("agent_queue")
                .select("id, complaint_id, priority_score")
                .eq("assigned_to", agent_id)
                .eq("status", "ASSIGNED")
                .order("priority_score")           # lowest priority first to reassign
                .limit(load - max_load)
                .execute()
            )

            for row in overflow.data or []:
                # Find another agent with capacity
                new_agent = find_best_agent(tier, "")
                if new_agent and new_agent != agent_id:
                    supabase.table("agent_queue").update({
                        "assigned_to": new_agent,
                        "assigned_at": now.isoformat(),
                        "updated_at":  now.isoformat(),
                    }).eq("id", row["id"]).execute()

                    supabase.table("complaints").update({
                        "assigned_agent_id": new_agent,
                    }).eq("complaint_id", row["complaint_id"]).execute()

                    logger.info(
                        "[WorkloadBalancer] reassigned complaint=%s from=%s to=%s",
                        row["complaint_id"], agent_id, new_agent,
                    )


# ── Scheduler entry-point ─────────────────────────────────────────────────────

def start_maintenance_scheduler() -> None:
    """
    Wire into APScheduler (or any cron library).

    Example (APScheduler):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(queue_rebalancer,        "interval", minutes=5)
        scheduler.add_job(sla_monitor,             "interval", minutes=1)
        scheduler.add_job(agent_workload_balancer, "interval", minutes=10)
        scheduler.start()
    """
    logger.info("[QueueMaintenance] scheduler wired — start it externally via APScheduler")


# ── Private helpers ───────────────────────────────────────────────────────────

def _notify_agent_sla_risk(agent_id: str, complaint_id: str, deadline_iso: str) -> None:
    """
    Notify agent that SLA breach is imminent.
    Production: email / Slack / dashboard push notification.
    """
    print(f"\n[SLA ALERT] Agent {agent_id}: Complaint {complaint_id} SLA deadline {deadline_iso}")
