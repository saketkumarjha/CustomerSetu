"""
KB Notification Service

Sends in-app and email notifications for KB enrichment events.

Production replacement:
    - In-app: push to a WebSocket channel or Supabase Realtime
    - Email:  SendGrid / SES via the existing email gateway config
    - Slack:  Incoming webhooks

For the prototype, all sends are simulated via logger.info() and optional
Supabase inserts into an admin_notifications table (if it exists).
"""

import logging
from datetime import datetime, timezone

from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class KBNotificationService:

    def notify_high_quality_entry(
        self,
        queue_id: int,
        category: str,
        issue_type: str,
        quality_score: float,
        tier_level: int,
    ) -> None:
        """
        Notifies admins when a high-quality KB entry is auto-generated.
        Candidate for auto-approval (quality >= 0.95).
        """
        title   = "High-Quality KB Entry Ready for Review"
        message = (
            f"A high-quality resolution has been generated.\n\n"
            f"Category:      {category}\n"
            f"Issue:         {issue_type or 'N/A'}\n"
            f"Quality Score: {quality_score:.2f}\n"
            f"Tier:          {tier_level}\n\n"
            f"This entry is a candidate for auto-approval."
        )
        action_url = f"/admin/kb/queue?id={queue_id}"

        self._send_notification(
            notification_type = "KB_HIGH_QUALITY",
            title             = title,
            message           = message,
            action_url        = action_url,
            priority          = "low",
            metadata          = {
                "queue_id":     queue_id,
                "quality_score": quality_score,
                "category":     category,
            },
        )

    def notify_queue_threshold_reached(self, queue_size: int) -> None:
        """Alert when the unprocessed enrichment queue grows large."""
        if queue_size < 50:
            return

        title   = f"KB Enrichment Queue Backlog: {queue_size} entries"
        message = (
            f"The KB enrichment queue has {queue_size} pending entries.\n\n"
            f"Recommendation: Review and bulk-approve high-quality entries at "
            f"/admin/kb/queue"
        )
        self._send_notification(
            notification_type = "KB_QUEUE_BACKLOG",
            title             = title,
            message           = message,
            action_url        = "/admin/kb/queue?filter=pending",
            priority          = "warning",
            metadata          = {"queue_size": queue_size},
        )

    def send_weekly_digest(self, stats: dict) -> None:
        """
        Weekly summary of KB enrichment activity.
        stats keys: unverified_entries, pending_queue, tier_breakdown, report
        """
        unverified = stats.get("unverified_entries", 0)
        pending    = stats.get("pending_queue", 0)

        title   = f"KB Enrichment Weekly Digest — {pending} Pending"
        message = stats.get("report", "See /admin/kb for details.")

        self._send_notification(
            notification_type = "KB_WEEKLY_DIGEST",
            title             = title,
            message           = message,
            action_url        = "/admin/kb/entries?verified=false",
            priority          = "info",
            metadata          = {
                "unverified_entries": unverified,
                "pending_queue":      pending,
            },
        )

    # ── Private helper ────────────────────────────────────────────────────────

    def _send_notification(
        self,
        notification_type: str,
        title:             str,
        message:           str,
        action_url:        str,
        priority:          str,
        metadata:          dict,
    ) -> None:
        """
        Simulates notification delivery.

        Production: replace print/logger with real gateways.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Console simulation (visible in development)
        logger.info(
            "[KBNotify] [%s] %s | %s", priority.upper(), title, action_url
        )
        print(f"\n{'─'*60}")
        print(f"[KB NOTIFICATION] {priority.upper()}")
        print(f"  Type    : {notification_type}")
        print(f"  Title   : {title}")
        print(f"  Message : {message[:120]}...")
        print(f"  Action  : {action_url}")
        print(f"{'─'*60}\n")

        # Best-effort insert into admin_notifications table
        try:
            get_supabase().table("admin_notifications").insert({
                "notification_type": notification_type,
                "title":             title,
                "message":           message,
                "action_url":        action_url,
                "priority":          priority,
                "metadata":          metadata,
                "read":              False,
                "created_at":        now,
            }).execute()
        except Exception:
            pass  # Table may not exist — non-fatal
