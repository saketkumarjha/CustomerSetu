"""
Signal Extraction Layer
=======================
Transforms a completed pipeline state into a normalised row in
`complaint_signals`.  Called once per complaint, immediately after
`_save_pipeline_outputs` writes to the `complaints` table.

Schema contract (must match the complaint_signals DDL):
    complaint_id            TEXT  UNIQUE
    event_type              TEXT  NOT NULL
    product                 TEXT
    compliance_category     TEXT
    severity                SMALLINT (1–5)
    sentiment               TEXT
    urgency_score           NUMERIC(5,4)
    financial_loss_flag     BOOLEAN
    financial_impact_amount NUMERIC(12,2)
    rbi_reportable          BOOLEAN
    channel                 TEXT
    channel_type            TEXT
    region                  TEXT
    customer_segment        TEXT
    is_duplicate            BOOLEAN
    created_at              TIMESTAMPTZ  (set by DB default — not sent here)
"""

import logging
import re
from typing import Any

from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# ── Normalisation maps ────────────────────────────────────────────────────────

# Maps pipeline category strings → product slugs used in clustering
_CATEGORY_TO_PRODUCT: dict[str, str] = {
    "home loan":                "home_loan",
    "personal loan":            "personal_loan",
    "auto loan":                "auto_loan",
    "credit card":              "credit_card",
    "debit card":               "debit_card",
    "savings account":          "savings_account",
    "current account":          "current_account",
    "fixed deposit":            "fixed_deposit",
    "recurring deposit":        "recurring_deposit",
    "upi":                      "upi",
    "neft":                     "neft",
    "rtgs":                     "rtgs",
    "imps":                     "imps",
    "atm":                      "atm",
    "net banking":               "net_banking",
    "mobile banking":            "mobile_banking",
    "insurance":                "insurance",
    "mutual fund":               "mutual_fund",
    "forex":                    "forex",
    "locker":                   "locker",
    "kyc":                      "kyc",
    "cheque":                   "cheque",
}

# Maps raw channel values → normalised channel_type buckets
_CHANNEL_TYPE_MAP: dict[str, str] = {
    "twitter":      "digital",
    "whatsapp":     "digital",
    "email":        "digital",
    "mobile_app":   "digital",
    "mobile app":   "digital",
    "web":          "digital",
    "chatbot":      "digital",
    "ivr":          "call_center",
    "call":         "call_center",
    "call_center":  "call_center",
    "phone":        "call_center",
    "branch":       "branch",
    "in_person":    "branch",
    "letter":       "branch",
    "atm":          "atm",
}

# Keywords in root_cause / compliance_category that signal financial loss
_FINANCIAL_LOSS_KEYWORDS = (
    "fraud", "unauthorized", "debit", "loss", "stolen", "scam",
    "phishing", "emi", "overcharge", "duplicate charge", "wrong debit",
)


def _normalise_product(category: str | None) -> str | None:
    """Map free-text category to a product slug."""
    if not category:
        return None
    key = category.strip().lower()
    # Exact match first
    if key in _CATEGORY_TO_PRODUCT:
        return _CATEGORY_TO_PRODUCT[key]
    # Partial match fallback
    for k, v in _CATEGORY_TO_PRODUCT.items():
        if k in key:
            return v
    # Slugify whatever we got so clustering still works
    return re.sub(r"[^a-z0-9]+", "_", key).strip("_")


def _normalise_channel_type(channel: str | None) -> str | None:
    if not channel:
        return None
    return _CHANNEL_TYPE_MAP.get(channel.strip().lower(), "other")


def _infer_event_type(state: dict[str, Any]) -> str:
    """
    Derive a normalised event_type slug from pipeline outputs.
    Priority: compliance_category > root_cause keywords > category fallback.
    """
    compliance = (state.get("compliance_category") or "").upper()
    root_cause = (state.get("root_cause") or "").lower()
    category   = (state.get("category") or "").lower()

    # Compliance-driven event types (most specific)
    if "UNAUTHORIZED_TRANSACTION" in compliance or "FRAUD" in compliance:
        if "emi" in root_cause or "debit" in root_cause:
            return "duplicate_emi_debit"
        if "apk" in root_cause or "phishing" in root_cause:
            return "apk_fraud"
        if "atm" in root_cause or "card" in root_cause:
            return "card_fraud"
        return "unauthorized_transaction_fraud"

    if "MONEY_MULE" in compliance:
        return "money_mule_fraud"

    if "KYC" in compliance:
        return "kyc_compliance_issue"

    if "INTEREST_RATE" in compliance or "OVERCHARGE" in compliance:
        return "interest_rate_overcharge"

    # Root-cause keyword matching
    if "atm" in root_cause and ("fail" in root_cause or "cash" in root_cause or "dispense" in root_cause):
        return "atm_cash_dispense_failure"

    if "upi" in root_cause and ("fail" in root_cause or "decline" in root_cause or "timeout" in root_cause):
        return "upi_payment_failure"

    if "neft" in root_cause or "rtgs" in root_cause or "imps" in root_cause:
        return "fund_transfer_failure"

    if "login" in root_cause or "otp" in root_cause or "password" in root_cause:
        return "digital_access_failure"

    if "emi" in root_cause:
        return "emi_processing_issue"

    if "interest" in root_cause:
        return "interest_calculation_issue"

    if "statement" in root_cause or "passbook" in root_cause:
        return "statement_error"

    # Category-level fallback
    slug = re.sub(r"[^a-z0-9]+", "_", category).strip("_")
    return slug or "unclassified_complaint"


def _infer_financial_loss(state: dict[str, Any]) -> bool:
    """Heuristic: does this complaint likely involve financial loss?"""
    texts = " ".join(filter(None, [
        state.get("root_cause"),
        state.get("compliance_category"),
        state.get("category"),
        state.get("complaint_text"),
    ])).lower()
    return any(kw in texts for kw in _FINANCIAL_LOSS_KEYWORDS)


async def extract_and_store_signals(
    complaint_id: str,
    state: dict[str, Any],
    customer_id: str | None = None,
) -> None:
    """
    Extract normalised signals from `state` and upsert into `complaint_signals`.

    `customer_id` must be passed explicitly from the caller because LangGraph
    does not guarantee that input-only fields like customer_id survive into
    final_state after all nodes have run.

    Uses upsert (ON CONFLICT on complaint_id) so re-running a pipeline
    updates the signal rather than duplicating it.
    """
    supabase = get_supabase()

    severity_raw = state.get("severity")
    # severity may come as int or string ("3", "HIGH" etc.)
    try:
        severity_int = int(severity_raw)
    except (TypeError, ValueError):
        # Map text severities to integers
        _sev_map = {"low": 1, "medium": 2, "moderate": 2, "high": 3, "critical": 4, "very high": 5}
        severity_int = _sev_map.get(str(severity_raw).lower(), None) if severity_raw else None

    # channel: prefer what the complaint came in on (initial_state["channel"]),
    # fall back to the notification channel chosen by the auto-responder.
    channel_raw = state.get("channel") or state.get("notification_channel")

    signal = {
        "complaint_id":            complaint_id,
        # customer_id comes from initial_state, not final_state — passed explicitly
        "customer_id":             customer_id or state.get("customer_id") or None,
        "event_type":              _infer_event_type(state),
        "product":                 _normalise_product(state.get("category")),
        "compliance_category":     state.get("compliance_category"),
        "severity":                severity_int,
        "sentiment":               state.get("sentiment"),
        "urgency_score":           state.get("urgency_score"),
        "financial_loss_flag":     _infer_financial_loss(state),
        "financial_impact_amount": None,          # not available from pipeline yet
        "rbi_reportable":          bool(state.get("is_rbi_reportable", False)),
        "channel":                 channel_raw,
        "channel_type":            _normalise_channel_type(channel_raw),
        "region":                  state.get("region"),          # populated if present in state
        "customer_segment":        state.get("customer_segment"),
        "is_duplicate":            bool(state.get("is_duplicate", False)),
    }

    try:
        result = (
            supabase.table("complaint_signals")
            .upsert(signal, on_conflict="complaint_id")
            .execute()
        )
        if result.data:
            logger.info(
                "[SIGNALS] Stored signal for %s — event_type=%s product=%s region=%s",
                complaint_id, signal["event_type"], signal["product"], signal["region"],
            )
        else:
            logger.warning("[SIGNALS] Upsert returned no data for %s", complaint_id)
    except Exception:
        # Signal extraction must NEVER crash the pipeline — log and continue
        logger.exception("[SIGNALS] Failed to store signal for %s", complaint_id)
