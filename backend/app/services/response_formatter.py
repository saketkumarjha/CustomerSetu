"""
Response Formatter

Converts Agent 8's draft_response into a tier-appropriate customer message.

Responsibilities:
  1. Load tier template (file-based → Python fallback)
  2. Inject contact info from ContactInfoService
  3. Inject escalation timeline from EscalationTimeline
  4. Format per channel: email/web/whatsapp (full) vs sms (compact)

Usage:
    from app.services.response_formatter import format_for_tier

    result = format_for_tier(
        draft_response  = state["draft_response"],
        tier_level      = state.get("current_tier", 1),
        complaint_id    = complaint_id,
        channel         = state.get("channel", "email"),
        sla_deadline    = state.get("rbi_tat_deadline"),
    )
    formatted_text = result["formatted_response"]
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from app.services.contact_info_service import get_tier_contacts
from app.utils.escalation_timeline import calculate_escalation_info

logger = logging.getLogger(__name__)

BANK_NAME   = "Union Bank of India"
BANK_SITE   = "www.unionbankofindia.co.in"
TOLL_FREE   = "1800-22-2244"

# Template directory — relative to this file's location
_TEMPLATE_BASE = os.path.join(
    os.path.dirname(__file__), "..", "templates", "tier_responses"
)


# ── Public API ────────────────────────────────────────────────────────────────

def format_for_tier(
    draft_response: str,
    tier_level: int,
    complaint_id: str,
    customer_name: str = "Valued Customer",
    issue_summary: str = "your recent complaint",
    channel: str = "email",
    sla_deadline: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict:
    """
    Format Agent 8's draft into a full, tier-appropriate customer message.

    Args:
        draft_response: Raw resolution text from Agent 8.
        tier_level:     Tier at which the complaint is being resolved (1–4).
        complaint_id:   Complaint reference number.
        customer_name:  Personalisation; defaults to "Valued Customer".
        issue_summary:  One-line issue description for the greeting.
        channel:        "email" | "sms" | "web" | "whatsapp"
        sla_deadline:   ISO datetime from RBI TAT; used for escalation timeline.
        scope_id:       Branch/zone ID for specific contact lookup.

    Returns dict:
        formatted_response: str — full text ready to send.
        preview:            str — first 150 chars for SSE/dashboard preview.
        contact_info:       dict — tier contact details injected.
        escalation_info:    dict — escalation timeline details injected.
        channel:            str — channel used.
        tier_level:         int
    """
    contact_info    = get_tier_contacts(tier_level, scope_id=scope_id)
    escalation_info = calculate_escalation_info(tier_level, sla_deadline)

    template_vars = {
        "bank_name":        BANK_NAME,
        "bank_site":        BANK_SITE,
        "toll_free":        TOLL_FREE,
        "complaint_id":     complaint_id,
        "customer_name":    customer_name,
        "issue_summary":    issue_summary,
        "draft_response":   draft_response,
        "tier_name":        contact_info["name"],
        "contact_phone":    contact_info["phone"],
        "contact_email":    contact_info["email"],
        "contact_hours":    contact_info["hours"],
        "contact_address":  contact_info["address"],
        "escalation_msg":   escalation_info["message"],
        "sla_deadline":     escalation_info["deadline_formatted"],
        "date_today":       datetime.now(timezone.utc).strftime("%d %B %Y"),
    }

    if channel == "sms":
        template_name = f"tier_{tier_level}_template_sms.txt"
        formatted = _render_template(template_name, template_vars) or _format_sms(template_vars)
    else:
        template_name = f"tier_{tier_level}_template.txt"
        formatted = _render_template(template_name, template_vars) or _format_full(template_vars)

    preview = formatted[:150] + ("..." if len(formatted) > 150 else "")

    return {
        "formatted_response": formatted,
        "preview":            preview,
        "contact_info":       contact_info,
        "escalation_info":    escalation_info,
        "channel":            channel,
        "tier_level":         tier_level,
    }


# ── Template loader ───────────────────────────────────────────────────────────

def _render_template(template_name: str, variables: dict) -> Optional[str]:
    """Load a template file and substitute {placeholders}. Returns None on any error."""
    path = os.path.normpath(os.path.join(_TEMPLATE_BASE, template_name))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        return raw.format_map(variables)
    except FileNotFoundError:
        return None
    except KeyError as exc:
        logger.warning("Template %s missing placeholder %s — using Python fallback", template_name, exc)
        return None


# ── Python fallback formatters ────────────────────────────────────────────────

def _format_full(v: dict) -> str:
    return "\n".join([
        f"{v['bank_name']} — Customer Care",
        f"Date: {v['date_today']}",
        "",
        f"Dear {v['customer_name']},",
        "",
        f"Thank you for contacting {v['bank_name']}. We have received and reviewed "
        f"{v['issue_summary']}.",
        "",
        "RESOLUTION",
        "----------",
        v["draft_response"],
        "",
        f"CONTACT — {v['tier_name']}",
        "----------",
        f"  Phone   : {v['contact_phone']}",
        f"  Email   : {v['contact_email']}",
        f"  Hours   : {v['contact_hours']}",
        f"  Address : {v['contact_address']}",
        "",
        "ESCALATION INFORMATION",
        "----------------------",
        v["escalation_msg"],
        "",
        f"Complaint Reference : {v['complaint_id']}",
        f"Track your complaint: {v['bank_site']}/complaint-tracking",
        "",
        "Regards,",
        "Customer Care Team",
        v["bank_name"],
        f"Toll-Free: {v['toll_free']}",
    ])


def _format_sms(v: dict) -> str:
    summary = v["draft_response"][:100]
    esc = v["escalation_msg"][:80] if len(v["escalation_msg"]) > 80 else v["escalation_msg"]
    return (
        f"UBI: Re complaint {v['complaint_id']}: {summary}. "
        f"Queries: {v['contact_phone']}. {esc}"
    )
