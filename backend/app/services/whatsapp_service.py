"""
WhatsApp Service — Twilio send helper + RAG instant reply logic.

This module lives inside the backend package so it can be imported
by both channels.py (webhook) and agent_action_service.py (reply on action).
"""

import uuid
import logging

logger = logging.getLogger(__name__)

# ── Twilio client (lazy) ──────────────────────────────────────────────────────

_twilio_client = None


def _get_twilio_client():
    global _twilio_client
    if _twilio_client is None:
        try:
            from twilio.rest import Client
            from app.core.config import get_settings
            s = get_settings()
            if not s.twilio_account_sid or not s.twilio_auth_token:
                raise ValueError("Twilio credentials not set in .env")
            _twilio_client = Client(s.twilio_account_sid, s.twilio_auth_token)
        except ImportError:
            raise RuntimeError("twilio not installed — run: pip install twilio")
    return _twilio_client


def send_whatsapp_reply(to_number: str, message: str) -> bool:
    """
    Send a WhatsApp message via Twilio REST API.
    Called by agent_action_service when channel == 'whatsapp'.
    """
    from app.core.config import get_settings
    s = get_settings()

    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    try:
        client = _get_twilio_client()
        client.messages.create(
            from_=s.twilio_whatsapp_number,
            to=to_number,
            body=message,
        )
        logger.info("[WHATSAPP] Reply sent to %s", to_number)
        return True
    except Exception as exc:
        logger.error("[WHATSAPP] Send failed to %s: %s", to_number, exc)
        return False


def send_feedback_survey_whatsapp(to_number: str, complaint_id: str, customer_id: str) -> bool:
    """
    Send a CSAT survey link to the customer via WhatsApp after complaint resolution.
    Called by feedback_survey_service for whatsapp channel complaints.
    """
    from app.core.config import get_settings
    import urllib.parse
    s = get_settings()

    encoded_cid = urllib.parse.quote(customer_id, safe="")
    feedback_url = f"{s.frontend_base_url.rstrip('/')}/feedback?id={complaint_id}&cid={encoded_cid}"

    message = (
        f"Dear Customer,\n\n"
        f"Your complaint *{complaint_id}* has been resolved by Union Bank of India.\n\n"
        f"We'd love your feedback! Please rate your experience here:\n"
        f"{feedback_url}\n\n"
        f"For any further help, call 1800-22-2244 (Toll Free).\n"
        f"Thank you for banking with us."
    )
    return send_whatsapp_reply(to_number, message)


# ── Tier detection ────────────────────────────────────────────────────────────

def detect_tier(text: str) -> int:
    """
    Returns 0 for general queries, 1+ for branch/escalation complaints.
    Used by both email and WhatsApp inbound handlers.

    Tier 0 — General inquiry / informational (RAG auto-reply)
    Tier 1 — Branch-level formal complaint (pipeline + human review)
    Tier 2 — Zonal escalation explicitly requested
    Tier 3 — Regional escalation explicitly requested
    Tier 4 — Head Office / Nodal
    Tier 5 — RBI Ombudsman
    """
    import re
    t = text.lower()

    # ── Tier 0 fast-exit: obvious general banking inquiries ──────────────────
    # If the message is clearly informational (no complaint signals at all),
    # bail early so we don't waste time scanning Tier 1+ keyword lists.
    _inquiry_openers = [
        "what is", "what are", "how do i", "how to", "how can i",
        "please tell me", "can you tell me", "could you please",
        "i want to know", "i would like to know", "i need information",
        "please let me know", "kindly let me know",
        "what is the interest rate", "what is the rate", "what is the process",
        "eligibility criteria", "documents required", "documentation needed",
        "how to open", "how to apply", "how to check", "how to link",
        "what is ifsc", "what is swift", "what is micr",
        "branch timing", "branch hours", "working hours", "atm location",
        "nearest atm", "nearest branch",
    ]
    # Only treat as Tier 0 if it's a clean inquiry — no negative/complaint words
    _complaint_signals = [
        "complaint", "issue", "problem", "not working", "failed", "failure",
        "deducted", "charged", "fraud", "dispute", "refund", "error",
        "wrong", "incorrect", "blocked", "frozen", "unauthorized",
        "grievance", "escalate", "disgusted", "frustrated", "angry",
        "harassment", "cheat", "scam",
    ]
    if (
        any(t.startswith(op) or t[t.find("subject:"):].lstrip("subject: ").startswith(op)
            for op in _inquiry_openers)
        and not any(sig in t for sig in _complaint_signals)
    ):
        return 0

    # ── Tier 5 — Ombudsman / RBI escalation ──────────────────────────────────
    if any(kw in t for kw in ["ombudsman", "rbi complaint", "banking ombudsman", "rbi ombudsman"]):
        return 5

    # ── Tier 4 — Head Office / Senior leadership ──────────────────────────────
    if any(kw in t for kw in ["ceo", "head office", "chairman", "managing director"]) \
            or re.search(r"\bmd\b", t):
        return 4

    # ── Tier 3 — Regional ─────────────────────────────────────────────────────
    if any(kw in t for kw in ["regional office", "regional manager", "regional head"]):
        return 3

    # ── Tier 2 — Zonal ───────────────────────────────────────────────────────
    if any(kw in t for kw in [
        "zonal office", "zone manager", "zonal head",
        "zonal officer", "area manager", "area office",
        "circle office", "circle head", "controlling office",
        "divisional office", "divisional manager",
        "cluster manager", "territory manager",
        "lead bank manager", "field general manager",
    ]):
        return 2

    # ── Tier 1 — Branch code pattern ─────────────────────────────────────────
    if re.search(r"br_[a-z]{2}_\d{3}", t):
        return 1

    # ── Tier 1 — Explicit complaint / grievance intent ────────────────────────
    if any(kw in t for kw in [
        "writing to raise a grievance", "raise a grievance", "raising a grievance",
        "lodge a complaint", "lodging a complaint", "formal complaint",
        "register a complaint", "registering a complaint",
        "file a complaint", "filing a complaint",
        "escalate this matter", "escalate to higher", "higher authorities",
        "approach rbi", "consumer forum",
        "want to complain", "wish to complain",
        "raise this issue", "bring to your notice",
        "i am writing to", "this is to bring",
    ]):
        return 1

    # ── Tier 1 — Digital payment & transaction failures ───────────────────────
    if any(kw in t for kw in [
        # UPI
        "upi failed", "upi failure", "upi not working", "upi blocked",
        "upi transaction not", "upi amount", "upi payment failed",
        # NEFT / RTGS / IMPS
        "neft failed", "neft not credited", "neft returned", "neft not received",
        "rtgs failed", "rtgs not credited", "rtgs not received",
        "imps failed", "imps not credited", "imps not received",
        # General transfer failures
        "transaction failed", "payment failed", "transfer failed",
        "money not credited", "amount not credited", "money not received",
        "amount not received", "fund not transferred", "funds not received",
        "payment not processed", "transaction pending since",
        "debited but not credited", "deducted but not received",
        "debited but not received", "amount debited not received",
        # Reversal not done
        "reversal not done", "reversal not credited", "reversal pending",
    ]):
        return 1

    # ── Tier 1 — Account, card & loan service failures ────────────────────────
    if any(kw in t for kw in [
        # Account issues
        "account blocked", "account frozen", "account suspended",
        "account closed without", "account deactivated", "account inactive",
        "account hold", "lien marked", "lien on account",
        # Card issues
        "card blocked", "card not received", "card not working",
        "card swallowed", "atm swallowed", "cash not dispensed",
        "atm cash not", "atm did not dispense", "cash not came out",
        # Cheque
        "cheque bounced", "cheque dishonoured", "cheque returned",
        "cheque not cleared", "clearing failed", "cheque pending",
        "dd not issued", "demand draft not", "pay order not",
        # Loan / EMI
        "emi deducted twice", "emi deducted double", "double emi",
        "emi not posted", "emi not credited", "emi bounced",
        "loan not disbursed", "loan amount not credited",
        "loan account not updated", "pre-emi not received",
        "moratorium not applied", "moratorium not given",
        # Salary / pension
        "salary not credited", "salary not received",
        "pension not credited", "pension not received",
        "scholarship not credited",
        # KYC / digital access
        "kyc rejected", "kyc not updated", "kyc blocked",
        "kyc pending", "kyc issue", "kyc not done",
        "net banking locked", "mobile banking blocked",
        "otp not received", "otp not coming",
        "internet banking not working", "mobile banking not working",
        "net banking not working", "app not working",
        # Statement / passbook
        "passbook not updated", "wrong entry in passbook",
        "incorrect statement", "statement error",
        "balance showing wrong", "wrong balance shown",
        "mini statement incorrect",
        # FD / RD
        "fd not matured", "fd maturity not credited", "fd amount not received",
        "rd not credited", "rd maturity pending",
        # Locker
        "locker not opened", "locker access denied", "locker broken",
        # Interest / charges complaint
        "interest not credited", "interest wrongly calculated",
        "excess interest charged", "penal interest wrongly",
    ]):
        return 1

    # ── Tier 1 — Branch staff complaint + negative / distress language ────────
    _branch_kw = [
        "branch manager", "branch staff", "branch visit",
        "visited the branch", "went to the branch", "at the branch",
        "branch officer", "counter staff", "relationship manager",
        "customer service officer", "bank employee", "bank official",
        "bank representative", "bank executive",
    ]
    _negative_kw = [
        # Emotional
        "worst", "bad", "terrible", "frustrated", "angry", "pathetic",
        "useless", "fraud", "cheat", "scam", "unprofessional", "rude", "poor",
        # Formal complaint language
        "denied", "distress", "hardship", "unacceptable", "no help",
        "no empathy", "no response", "no resolution", "no assistance",
        "harassment", "misbehavior", "negligence", "mental distress",
        "shock", "deeply concerned", "urgently request",
        # Additional distress signals
        "humiliated", "insulted", "ignored", "disrespectful",
        "misbehaved", "misconduct", "irresponsible", "incompetent",
        "not cooperative", "not helpful", "refused to help",
        "turned away", "sent back", "not attended",
    ]
    if any(kw in t for kw in _branch_kw) and any(kw in t for kw in _negative_kw):
        return 1

    # ── Tier 1 — Specific financial disputes (unauthorised / erroneous charges) ─
    if any(kw in t for kw in [
        "unauthorized transaction", "unauthorised transaction",
        "wrongly charged", "incorrectly debited", "erroneous charge",
        # Non-maintenance charge variants
        "non-maintenance charge", "non-maintenance fee", "non-maintenance",
        "minimum balance charge", "average balance charge",
        "sms charge", "annual fee charged", "renewal fee charged",
        # Deduction variants
        "deducted without", "deducted due to", "amount deducted",
        "balance deducted", "money deducted", "wrongly deducted",
        "incorrectly deducted", "fraudulently deducted",
        "charged without notice", "charged without my consent",
        "charged without permission", "charged without intimation",
        "not authorized", "chargeback",
        # Duplicate debits
        "double debit", "duplicate debit", "double deduction",
        "duplicate charge", "charged twice", "debited twice",
        # Refund context
        "requesting a refund", "request a refund", "refund of ₹",
        "refund of rs", "refund the amount", "amount not refunded",
        "refund not received", "refund pending", "refund not processed",
        # Insurance mis-selling
        "insurance deducted", "premium deducted without", "insurance charged",
        # Reward / cashback not received
        "cashback not received", "reward points not credited",
        "offer not applied", "discount not applied",
    ]):
        return 1

    # ── Tier 1 — Fraud / security concerns ───────────────────────────────────
    if any(kw in t for kw in [
        "my account was hacked", "account hacked", "account compromised",
        "someone accessed my account", "unknown transaction",
        "suspicious transaction", "fraudulent transaction",
        "phishing", "vishing", "sim swap", "sim swapped",
        "card cloned", "card skimmed", "skimming",
        "otp shared unknowingly", "cyber fraud",
        "lost my card", "card stolen", "card misused",
        "mobile banking fraud", "net banking fraud",
    ]):
        return 1

    return 0


# ── Instant RAG reply (Tier 0) ────────────────────────────────────────────────

def instant_rag_reply(message_text: str) -> str:
    """
    Classify → RAG retrieve → GPT-4o draft → return reply string.
    Runs synchronously; wrap with asyncio.to_thread() from async context.
    """
    from openai import OpenAI
    from app.core.config import get_settings
    from app.services.agents.fanout_agents import _classify_sync
    from app.services.agents.rag_agent import retrieve_context

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # Classify
    try:
        cls = _classify_sync(message_text)
        category = cls.get("category", "General Banking")
    except Exception:
        category = "General Banking"

    # RAG
    try:
        rag = retrieve_context(masked_text=message_text, category=category, n=3)
        docs = rag.get("documents", [])
    except Exception:
        docs = []

    kb_context = "\n\n".join(
        f"[KB {i+1}] {d['resolution_text'][:400]}" for i, d in enumerate(docs)
    ) if docs else "No specific KB entry found."

    system_prompt = (
        "You are a helpful customer service agent for Union Bank of India. "
        "Reply to the customer's WhatsApp message in max 3 sentences. "
        "Use the knowledge base context to answer accurately. "
        "If you cannot answer from context, say you will escalate to a specialist. "
        "Do NOT invent account numbers, transaction IDs, or amounts. "
        "Be warm and professional."
    )
    user_prompt = (
        f"Customer message: {message_text}\n\n"
        f"Knowledge base context:\n{kb_context}\n\n"
        "Write a concise WhatsApp reply:"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("[WHATSAPP] RAG reply generation failed: %s", exc)
        return (
            "Thank you for contacting Union Bank of India. "
            "Our team will assist you shortly. "
            "For urgent help, call 1800-22-2244."
        )


# ── Save complaint to DB ──────────────────────────────────────────────────────

def save_whatsapp_complaint(customer_number: str, message_text: str, tier: int) -> str:
    """Insert a WhatsApp complaint into the DB and return complaint_id."""
    from app.db.supabase_client import get_supabase
    supabase = get_supabase()

    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
    supabase.table("complaints").insert({
        "complaint_id":             complaint_id,
        "customer_id":              customer_number,
        "channel":                  "whatsapp",
        "original_text":            message_text,
        "merged_text":              message_text,
        "pipeline_status":          "pending",
        "status":                   "pending",
        "initial_tier":             tier,
        "current_tier":             tier,
        "assigned_tier":            max(tier, 1),
        "max_tier_reached":         tier,
        "total_escalations_count":  0,
        "escalation_count":         0,
        "escalation_path":          [],
        "is_escalating":            False,
        "escalation_loop_detected": False,
        "tier_locked":              False,
        "shadow_overridden":        False,
        "is_duplicate":             False,
        "is_rbi_reportable":        False,
        "rbi_reportable":           False,
        "action_steps":             [],
        "grounding_warnings":       [],
        "missing_info_indicators":  [],
        "context_documents":        [],
    }).execute()
    return complaint_id
