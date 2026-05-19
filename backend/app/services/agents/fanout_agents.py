"""
Parallel Fan-out Agents — 4 GPT-4o Agents Running Simultaneously

Agents:
1. Classification Agent — complaint category + product identification
2. Sentiment Agent     — emotion + urgency score + escalation flag
3. Compliance Agent    — RBI category detection + supervisor override
4. Severity Agent      — rule-based score + severity level 1-5

All 4 run via asyncio.gather() — total latency = max(individual) not sum.
Typical: 3-5s parallel vs 12-20s serial.

Each agent returns standardised AgentOutput with full XAI reasoning.
GPT-4o structured output (response_format=json_object) ensures
parseable responses without markdown fences.
"""

import asyncio
import json
import time
from openai import OpenAI
from app.core.config import get_settings
from app.models.agent_output import AgentOutput, AgentStatus

# Module-level singleton
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=60.0,    # 60s total — GPT-4o fan-out agents are parallel, keep generous
            max_retries=1,   # one automatic retry on transient 5xx, then fail fast
        )
    return _client


def _call_gpt4o(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> dict:
    """
    Synchronous GPT-4o call with JSON output enforced.
    Wrapped with asyncio.to_thread() in all async agent functions.

    Using response_format=json_object eliminates need for regex JSON extraction.
    Temperature=0.1 for consistent, deterministic outputs.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=max_tokens,
    )
    return json.loads(response.choices[0].message.content)


# ── AGENT 1: Classification Agent ────────────────────────────────────────────

CLASSIFICATION_SYSTEM = """You are a banking complaint classification specialist 
at an Indian bank. Classify customer complaints accurately.

You must respond ONLY with a valid JSON object in this exact format:
{
  "category": "<one of the categories below>",
  "product": "<specific product mentioned>",
  "confidence": <float 0.0-1.0>,
  "evidence_tokens": ["<word1>", "<word2>", "<word3>"],
  "runner_up_category": "<second most likely category>",
  "runner_up_confidence": <float 0.0-1.0>,
  "reasoning": "<explain why you chose this category in 2 sentences>"
}

Valid categories:
- Credit Card
- Debit Card  
- UPI / IMPS / NEFT
- Savings Account
- Current Account
- Home Loan
- Personal Loan
- Vehicle Loan
- Fixed Deposit
- Insurance
- KYC / Account Opening
- Internet Banking / Mobile App
- ATM
- Investment / Mutual Fund
- General Banking"""


def _classify_sync(masked_text: str) -> dict:
    user_prompt = f"""Classify this customer complaint:

COMPLAINT: {masked_text}

Remember: respond ONLY with the JSON object."""
    return _call_gpt4o(CLASSIFICATION_SYSTEM, user_prompt, max_tokens=300)


async def run_classification_agent(masked_text: str) -> AgentOutput:
    """Classification Agent — identifies complaint category and product."""
    start = time.perf_counter()

    try:
        result = await asyncio.to_thread(_classify_sync, masked_text)

        category = result.get("category", "General Banking")
        product = result.get("product", "Unknown")
        confidence = float(result.get("confidence", 0.5))
        evidence = result.get("evidence_tokens", [])
        runner_up = result.get("runner_up_category", "")
        runner_up_conf = result.get("runner_up_confidence", 0.0)
        gpt_reasoning = result.get("reasoning", "")

        reasoning = (
            f"Category: {category} (confidence: {confidence:.1%})\n"
            f"Product identified: {product}\n"
            f"Evidence tokens: {', '.join(evidence[:5]) if evidence else 'none'}\n"
            f"Runner-up: {runner_up} ({runner_up_conf:.1%})\n"
            f"GPT-4o reasoning: {gpt_reasoning}"
        )

        return AgentOutput(
            agent_name="Classification Agent",
            agent_order=3,
            status=AgentStatus.COMPLETE,
            decision=f"{category} — {product}",
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence[:5],
            metadata={
                "category": category,
                "product": product,
                "runner_up": runner_up,
                "runner_up_confidence": runner_up_conf,
            },
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    except Exception as e:
        return AgentOutput(
            agent_name="Classification Agent",
            agent_order=3,
            status=AgentStatus.FAILED,
            decision="General Banking (fallback)",
            confidence=0.0,
            reasoning=f"Classification failed: {str(e)}. Defaulting to General Banking.",
            metadata={"category": "General Banking", "error": str(e)},
            error_message=str(e),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )


# ── AGENT 2: Sentiment Agent ──────────────────────────────────────────────────

SENTIMENT_SYSTEM = """You are an expert in customer emotion analysis for 
Indian banking complaints. Detect emotion, urgency, and escalation signals.

Respond ONLY with a valid JSON object in this exact format:
{
  "emotion": "<one of: Calm, Concerned, Frustrated, Angry, Furious>",
  "urgency_score": <integer 1-10>,
  "escalation_flag": <true/false>,
  "escalation_reason": "<why escalation is needed, or null>",
  "trigger_phrases": ["<phrase1>", "<phrase2>"],
  "confidence": <float 0.0-1.0>,
  "reasoning": "<2 sentence explanation of emotion detection>"
}

Emotion scale:
- Calm (1-3 urgency): polite inquiry, no emotional language
- Concerned (3-5 urgency): worried, slightly anxious
- Frustrated (5-7 urgency): repeated issue, disappointed, time pressure
- Angry (7-9 urgency): strong negative language, demands action
- Furious (9-10 urgency): threatening, mentions legal/RBI, abusive

Escalation triggers: legal threats, mentions of RBI/consumer court,
financial loss > ₹10000, repeat complaint, media threats."""


def _sentiment_sync(masked_text: str) -> dict:
    user_prompt = f"""Analyze the emotion and urgency in this banking complaint:

COMPLAINT: {masked_text}

Respond ONLY with the JSON object."""
    return _call_gpt4o(SENTIMENT_SYSTEM, user_prompt, max_tokens=300)


async def run_sentiment_agent(masked_text: str) -> AgentOutput:
    """Sentiment Agent — emotion detection, urgency score, escalation flag."""
    start = time.perf_counter()

    try:
        result = await asyncio.to_thread(_sentiment_sync, masked_text)

        emotion = result.get("emotion", "Neutral")
        urgency = int(result.get("urgency_score", 5))
        escalation = bool(result.get("escalation_flag", False))
        escalation_reason = result.get("escalation_reason")
        triggers = result.get("trigger_phrases", [])
        confidence = float(result.get("confidence", 0.5))
        gpt_reasoning = result.get("reasoning", "")

        reasoning = (
            f"Emotion detected: {emotion} (confidence: {confidence:.1%})\n"
            f"Urgency score: {urgency}/10\n"
            f"Escalation required: {'YES' if escalation else 'NO'}"
            + (f" — {escalation_reason}" if escalation_reason else "") + "\n"
            f"Trigger phrases: {', '.join(triggers[:4]) if triggers else 'none'}\n"
            f"GPT-4o reasoning: {gpt_reasoning}"
        )

        return AgentOutput(
            agent_name="Sentiment Agent",
            agent_order=4,
            status=AgentStatus.COMPLETE,
            decision=f"{emotion} (Urgency: {urgency}/10)"
                     + (" ⚠️ ESCALATION" if escalation else ""),
            confidence=confidence,
            reasoning=reasoning,
            evidence=triggers[:4],
            metadata={
                "emotion": emotion,
                "urgency_score": urgency,
                "escalation_flag": escalation,
                "escalation_reason": escalation_reason,
            },
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    except Exception as e:
        return AgentOutput(
            agent_name="Sentiment Agent",
            agent_order=4,
            status=AgentStatus.FAILED,
            decision="Neutral — fallback (5/10 urgency)",
            confidence=0.0,
            reasoning=f"Sentiment detection failed: {str(e)}. Defaulting to Neutral.",
            metadata={"emotion": "Neutral", "urgency_score": 5, "escalation_flag": False},
            error_message=str(e),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )


# ── AGENT 3: Compliance Agent ─────────────────────────────────────────────────

COMPLIANCE_SYSTEM = """You are an RBI (Reserve Bank of India) compliance 
specialist. Identify if a banking complaint falls under any RBI-regulated 
category that requires mandatory reporting or escalation.

Respond ONLY with a valid JSON object in this exact format:
{
  "rbi_category": "<category from list below or NOT_APPLICABLE>",
  "is_rbi_reportable": <true/false>,
  "regulation_reference": "<RBI circular or guideline name, or null>",
  "supervisor_override": "<FORCE_HUMAN_REVIEW or null>",
  "auto_penalty_applicable": <true/false>,
  "penalty_details": "<penalty amount and trigger, or null>",
  "confidence": <float 0.0-1.0>,
  "evidence": ["<phrase1>", "<phrase2>"],
  "reasoning": "<2 sentence explanation>"
}

RBI Categories:
- UNAUTHORIZED_TRANSACTION_FRAUD: money debited without consent
- FAILED_TRANSACTION_TAT_BREACH: debit without credit, ATM failure, refund delayed
- UPI_BBPS_SETTLEMENT_ISSUE: UPI/IMPS/BBPS failures
- RECOVERY_AGENT_HARASSMENT: threatening calls, odd-hour calls, family contact
- DELAY_IN_PROPERTY_DOC_RELEASE: docs not returned after loan repayment
- UNFAIR_LOAN_CHARGES_OR_RATES: hidden fees, moratorium interest, opaque rate changes
- DELAY_IN_CARD_CLOSURE: card not closed within 7 working days
- UNSOLICITED_CARD_ISSUANCE: card issued or limit upgraded without consent
- HIDDEN_CARD_CHARGES: unexplained annual fees or late charges
- CREDIT_BUREAU_MISREPORTING: wrong CIBIL/Experian report, not updated in 30 days
- KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE: account frozen without prior notice
- MIS_SELLING_OF_PRODUCTS: insurance/MF sold disguised as FD or loan requirement
- NON_ADHERENCE_TO_FPC: Fair Practices Code violation
- NOT_APPLICABLE: complaint does not fall under any RBI-regulated category

supervisor_override rules:
- RECOVERY_AGENT_HARASSMENT → ALWAYS set to FORCE_HUMAN_REVIEW
- UNAUTHORIZED_TRANSACTION_FRAUD → FORCE_HUMAN_REVIEW
- UNSOLICITED_CARD_ISSUANCE → FORCE_HUMAN_REVIEW
- All others → null (normal routing applies)"""


def _compliance_sync(masked_text: str) -> dict:
    user_prompt = f"""Analyze this banking complaint for RBI compliance:

COMPLAINT: {masked_text}

Respond ONLY with the JSON object."""
    return _call_gpt4o(COMPLIANCE_SYSTEM, user_prompt, max_tokens=400)


async def run_compliance_agent(masked_text: str) -> AgentOutput:
    """Compliance Agent — RBI category detection + supervisor override rules."""
    start = time.perf_counter()

    try:
        result = await asyncio.to_thread(_compliance_sync, masked_text)

        rbi_category = result.get("rbi_category", "NOT_APPLICABLE")
        is_reportable = bool(result.get("is_rbi_reportable", False))
        regulation = result.get("regulation_reference")
        override = result.get("supervisor_override")
        penalty = bool(result.get("auto_penalty_applicable", False))
        penalty_details = result.get("penalty_details")
        confidence = float(result.get("confidence", 0.5))
        evidence = result.get("evidence", [])
        gpt_reasoning = result.get("reasoning", "")

        reasoning = (
            f"RBI Category: {rbi_category}\n"
            f"RBI Reportable: {'YES ⚠️' if is_reportable else 'NO'}\n"
            + (f"Regulation: {regulation}\n" if regulation else "")
            + (f"Supervisor Override: {override} 🚨\n" if override else "")
            + (f"Auto-penalty applicable: YES — {penalty_details}\n" if penalty else "")
            + f"Evidence: {', '.join(evidence[:4]) if evidence else 'none'}\n"
            f"GPT-4o reasoning: {gpt_reasoning}"
        )

        return AgentOutput(
            agent_name="Compliance Agent",
            agent_order=5,
            status=AgentStatus.COMPLETE,
            decision=(
                f"{rbi_category}"
                + (" ⚠️ RBI REPORTABLE" if is_reportable else "")
                + (" 🚨 OVERRIDE" if override else "")
            ),
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence[:4],
            metadata={
                "rbi_category": rbi_category,
                "is_rbi_reportable": is_reportable,
                "regulation_reference": regulation,
                "supervisor_override": override,
                "auto_penalty_applicable": penalty,
                "penalty_details": penalty_details,
            },
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    except Exception as e:
        return AgentOutput(
            agent_name="Compliance Agent",
            agent_order=5,
            status=AgentStatus.FAILED,
            decision="NOT_APPLICABLE (fallback — detection failed)",
            confidence=0.0,
            reasoning=f"Compliance detection failed: {str(e)}. Defaulting to NOT_APPLICABLE.",
            metadata={"rbi_category": "NOT_APPLICABLE", "is_rbi_reportable": False},
            error_message=str(e),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )


# ── AGENT 4: Severity Agent ───────────────────────────────────────────────────

SEVERITY_SYSTEM = """You are a complaint severity assessor at an Indian bank.
Evaluate the severity of customer complaints using a structured scoring system.

Respond ONLY with a valid JSON object in this exact format:
{
  "severity_level": <integer 1-5>,
  "severity_score": <float 1.0-10.0>,
  "severity_label": "<one of: Low, Moderate, High, Critical, Emergency>",
  "scoring_breakdown": {
    "financial_loss_mentioned": <true/false>,
    "amount_above_10000": <true/false>,
    "legal_threat_language": <true/false>,
    "repeat_complaint_signal": <true/false>,
    "time_sensitive": <true/false>,
    "safety_concern": <true/false>
  },
  "confidence": <float 0.0-1.0>,
  "reasoning": "<2 sentence explanation>"
}

Severity scale:
1 (Low, score 1-2):       Minor inconvenience, cosmetic issue, general query
2 (Moderate, score 3-4):  General dissatisfaction, delayed response
3 (High, score 5-6):      Significant impact, financial concern, time pressure  
4 (Critical, score 7-8):  Financial loss, RBI category, legal threat
5 (Emergency, score 9-10): Large financial loss + legal threat + RBI category

Scoring rules:
+2 financial loss mentioned
+2 amount > ₹10,000 implied
+2 legal/RBI threat language
+1 repeat complaint signal
+1 time-sensitive language
+2 safety concern
Max raw score = 10. Map to 1-5 scale."""


def _severity_sync(masked_text: str) -> dict:
    user_prompt = f"""Assess the severity of this banking complaint:

COMPLAINT: {masked_text}

Respond ONLY with the JSON object."""
    return _call_gpt4o(SEVERITY_SYSTEM, user_prompt, max_tokens=300)


async def run_severity_agent(masked_text: str) -> AgentOutput:
    """Severity Agent — rule-based scoring + GPT-4o validation."""
    start = time.perf_counter()

    try:
        result = await asyncio.to_thread(_severity_sync, masked_text)

        severity = int(result.get("severity_level", 3))
        severity = max(1, min(5, severity))  # clamp to 1-5
        score = float(result.get("severity_score", 5.0))
        label = result.get("severity_label", "High")
        breakdown = result.get("scoring_breakdown", {})
        confidence = float(result.get("confidence", 0.5))
        gpt_reasoning = result.get("reasoning", "")

        # Build breakdown string for XAI
        breakdown_lines = []
        score_map = {
            "financial_loss_mentioned": ("Financial loss mentioned", "+2"),
            "amount_above_10000": ("Amount > ₹10,000", "+2"),
            "legal_threat_language": ("Legal/RBI threat language", "+2"),
            "repeat_complaint_signal": ("Repeat complaint signal", "+1"),
            "time_sensitive": ("Time-sensitive language", "+1"),
            "safety_concern": ("Safety concern", "+2"),
        }
        for key, (label_str, points) in score_map.items():
            if breakdown.get(key):
                breakdown_lines.append(f"  ✓ {label_str}: {points} points")

        breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else "  No escalating factors detected"

        reasoning = (
            f"Severity: {severity}/5 — {label} (score: {score:.1f}/10)\n"
            f"Scoring breakdown:\n{breakdown_text}\n"
            f"GPT-4o reasoning: {gpt_reasoning}"
        )

        return AgentOutput(
            agent_name="Severity Agent",
            agent_order=6,
            status=AgentStatus.COMPLETE,
            decision=f"Severity {severity}/5 — {label} (score: {score:.1f}/10)",
            confidence=confidence,
            reasoning=reasoning,
            evidence=[k for k, v in breakdown.items() if v],
            metadata={
                "severity_level": severity,
                "severity_score": score,
                "severity_label": label,
                "scoring_breakdown": breakdown,
            },
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    except Exception as e:
        return AgentOutput(
            agent_name="Severity Agent",
            agent_order=6,
            status=AgentStatus.FAILED,
            decision="Severity 3/5 — High (fallback)",
            confidence=0.0,
            reasoning=f"Severity assessment failed: {str(e)}. Defaulting to Severity 3.",
            metadata={"severity_level": 3, "severity_score": 5.0, "severity_label": "High"},
            error_message=str(e),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )


# ── PARALLEL RUNNER — all 4 agents simultaneously ────────────────────────────

async def run_parallel_fanout(masked_text: str) -> dict:
    """
    Execute all 4 agents simultaneously via asyncio.gather().

    Total latency = max(individual agent latency) ≈ 3-5s
    vs serial execution ≈ 12-20s

    Per-agent error handling ensures one failure doesn't block others.
    Each agent has its own try/except with safe defaults.

    Returns dict of all 4 agent outputs for the Supervisor.
    """
    classification, sentiment, compliance, severity = await asyncio.gather(
        run_classification_agent(masked_text),
        run_sentiment_agent(masked_text),
        run_compliance_agent(masked_text),
        run_severity_agent(masked_text),
    )

    return {
        "classification": classification,
        "sentiment": sentiment,
        "compliance": compliance,
        "severity": severity,
    }