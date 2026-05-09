"""
Resolution Event Handler

Integration layer between the pipeline / agent actions and the KB enrichment
manager.  Each public method is an event hook that the calling code fires
after a resolution milestone occurs.

Integration points:
    Route 1 (Auto-Response):
        graph.py → routing_node → on_auto_response_sent()

    Route 2 (Human Review):
        agent_action_service.py → handle_accept()  → on_agent_action(action="ACCEPT")
        agent_action_service.py → handle_edit()    → on_agent_action(action="EDIT")
        agent_action_service.py → handle_reject()  → on_agent_action(action="REJECT")

    Customer CSAT:
        feedback.py → on_customer_feedback()
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.db.supabase_client import get_supabase
from app.tasks.kb_enrichment import (
    KBEnrichmentManager,
    TYPE_AUTO_RESPONSE,
    TYPE_AGENT_ACCEPTED,
    TYPE_AGENT_EDITED,
)

logger = logging.getLogger(__name__)


class ResolutionEventHandler:

    def __init__(self) -> None:
        self._manager = KBEnrichmentManager()

    # ── Route 1: Auto-response ────────────────────────────────────────────────

    def on_auto_response_sent(self, complaint_id: str) -> None:
        """
        Called immediately after Route 1 sends an auto-response.

        The 24-hour wait before KB addition is handled by
        schedule_kb_enrichment() (asyncio task) which is still called from
        graph.py.  This hook is reserved for any immediate side-effects
        that should fire right after the send (e.g. audit log, metrics).
        """
        logger.info(
            "[ResolutionEvent] Auto-response sent for %s — 24-h enrichment timer started",
            complaint_id,
        )

    # ── Route 2: Human review ─────────────────────────────────────────────────

    def on_agent_action(
        self,
        complaint_id: str,
        agent_id: str,
        action: str,
        action_data: Optional[dict] = None,
    ) -> Optional[int]:
        """
        Called after a human agent takes an action on a complaint.

        action:       "ACCEPT" | "EDIT" | "REJECT" | "MANUAL_ESCALATE"
        action_data:  dict with optional keys:
                        edited_response, notes, escalation_target_tier
        Returns the kb_enrichment_queue id (or None if not enqueued).
        """
        if action_data is None:
            action_data = {}

        if action == "REJECT" or action == "MANUAL_ESCALATE":
            logger.info(
                "[ResolutionEvent] Agent %s on %s: %s — not enriching KB",
                agent_id, complaint_id, action,
            )
            return None

        complaint = self._fetch_complaint(complaint_id)
        if not complaint:
            return None

        if action == "ACCEPT":
            resolution_event = {
                "type":             TYPE_AGENT_ACCEPTED,
                "resolution_text":  complaint.get("draft_response", ""),
                "confidence_score": float(complaint.get("confidence_score") or 0.5),
                "agent_action":     "ACCEPT",
                "agent_id":         agent_id,
            }

        elif action == "EDIT":
            resolution_event = {
                "type":             TYPE_AGENT_EDITED,
                "resolution_text":  action_data.get("edited_response", ""),
                "edited_response":  action_data.get("edited_response", ""),
                "confidence_score": float(complaint.get("confidence_score") or 0.5),
                "agent_action":     "EDIT",
                "agent_id":         agent_id,
                "edit_notes":       action_data.get("notes", ""),
            }

        else:
            return None

        queue_id = self._manager.enqueue_for_enrichment(complaint, resolution_event)

        if queue_id:
            logger.info(
                "[ResolutionEvent] %s action on %s → KB queue entry %d",
                action, complaint_id, queue_id,
            )
            self._notify_if_high_quality(queue_id, complaint, resolution_event)

        return queue_id

    # ── Customer CSAT ─────────────────────────────────────────────────────────

    def on_customer_feedback(
        self,
        complaint_id: str,
        rating: float,
        comment: str = "",
    ) -> None:
        """
        Called when a customer submits a CSAT rating (1–5).

        Updates the pending queue entry's quality signals if one exists, or
        adds the complaint to the queue if CSAT >= 4 and it wasn't queued.
        """
        supabase = get_supabase()

        # Update complaint record
        try:
            supabase.table("complaints").update({
                "customer_feedback_score": rating,
                "customer_feedback_text":  comment,
                "customer_feedback_at":    datetime.now(timezone.utc).isoformat(),
            }).eq("complaint_id", complaint_id).execute()
        except Exception as exc:
            logger.warning("[ResolutionEvent] CSAT complaint update failed: %s", exc)

        # Check if a pending queue entry exists
        try:
            queue_rows = (
                supabase.table("kb_enrichment_queue")
                .select("id, resolution_type, confidence_score")
                .eq("complaint_id", complaint_id)
                .eq("processed", False)
                .execute()
                .data or []
            )
        except Exception as exc:
            logger.warning("[ResolutionEvent] CSAT queue lookup failed: %s", exc)
            return

        if queue_rows:
            # Recalculate quality with updated CSAT
            complaint = self._fetch_complaint(complaint_id)
            if not complaint:
                return
            complaint["customer_feedback_score"] = rating

            resolution_type = queue_rows[0].get("resolution_type", TYPE_AUTO_RESPONSE)
            resolution_event = {
                "type":             resolution_type,
                "confidence_score": float(queue_rows[0].get("confidence_score") or 0.5),
            }
            quality = self._manager.calculate_quality_signals(complaint, resolution_event)

            try:
                supabase.table("kb_enrichment_queue").update({
                    "customer_feedback_score":   rating,
                    "recommended_quality_score": quality["score"],
                    "quality_signals_json":      quality,
                }).eq("id", queue_rows[0]["id"]).execute()
                logger.info(
                    "[ResolutionEvent] Updated queue entry %d with CSAT %.1f → Q %.2f",
                    queue_rows[0]["id"], rating, quality["score"],
                )
            except Exception as exc:
                logger.warning("[ResolutionEvent] CSAT queue update failed: %s", exc)

        elif rating >= 4:
            # High CSAT but not yet queued — add now
            complaint = self._fetch_complaint(complaint_id)
            if complaint:
                complaint["customer_feedback_score"] = rating
                resolution_type = complaint.get("response_tier", TYPE_AUTO_RESPONSE)
                resolution_event = {
                    "type":             resolution_type,
                    "resolution_text":  complaint.get("final_response_text", ""),
                    "confidence_score": float(complaint.get("confidence_score") or 0.5),
                }
                self._manager.enqueue_for_enrichment(complaint, resolution_event)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_complaint(self, complaint_id: str) -> Optional[dict]:
        supabase = get_supabase()
        try:
            result = (
                supabase.table("complaints")
                .select(
                    "complaint_id, status, category, masked_text, "
                    "draft_response, final_response_text, "
                    "confidence_score, current_tier, tier_resolved_at, "
                    "branch_id, customer_feedback_score, compliance_category, "
                    "escalation_count, is_duplicate, response_tier"
                )
                .eq("complaint_id", complaint_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("[ResolutionEvent] Could not fetch complaint %s: %s", complaint_id, exc)
            return None

    def _notify_if_high_quality(
        self,
        queue_id: int,
        complaint: dict,
        resolution_event: dict,
    ) -> None:
        """Fire-and-forget notification for high-quality auto-approve candidates."""
        quality = self._manager.calculate_quality_signals(complaint, resolution_event)
        if quality["score"] >= KBEnrichmentManager.AUTO_APPROVE_THRESHOLD:
            try:
                from app.services.kb_notification_service import KBNotificationService
                KBNotificationService().notify_high_quality_entry(
                    queue_id=queue_id,
                    category=complaint.get("category", "General Banking"),
                    issue_type=complaint.get("issue_type", ""),
                    quality_score=quality["score"],
                    tier_level=int(
                        complaint.get("tier_resolved_at") or complaint.get("current_tier") or 1
                    ),
                )
            except Exception as exc:
                logger.debug("[ResolutionEvent] Notification failed: %s", exc)


# ── Module-level singleton ────────────────────────────────────────────────────

resolution_event_handler = ResolutionEventHandler()
