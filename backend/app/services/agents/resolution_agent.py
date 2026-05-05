"""
Resolution Generator — GPT-4o with Dynamic Few-Shot Prompting

Strategy:
1. Build a dynamic system prompt using all upstream agent outputs
2. Inject retrieved RAG context as numbered few-shot examples
3. Apply per-category confidence thresholds for routing
4. Return structured JSON: draft, root_cause, action_steps, confidence

Why dynamic few-shot (not static):
  Static prompts give the same template to every complaint.
  Dynamic prompts inject the top-3 most similar past resolutions
  as examples. The model produces responses that match the proven
  style and structure of your best historical resolutions.

RBI compliance in prompts:
  The system prompt instructs the model to avoid unverifiable
  specific commitments (exact amounts, exact dates) without
  an agent verifying first. These become grounding warnings.
"""

import json
import time
from openai import OpenAI
from app.core.config import get_settings

_client: OpenAI | None = None

# Per-category confidence thresholds
# Below these → always route to human review regardless of risk score
CATEGORY_CONFIDENCE_THRESHOLDS = {
    "Credit Card": 0.85,
    "Debit Card": 0.85,
    "UPI / IMPS / NEFT": 0.82,
    "Savings Account": 0.80,
    "Current Account": 0.80,
    "Home Loan": 0.88,
    "Personal Loan": 0.88,
    "Vehicle Loan": 0.88,
    "Fixed Deposit": 0.82,
    "Insurance": 0.90,
    "KYC / Account Opening": 0.78,
    "Internet Banking / Mobile App": 0.80,
    "ATM": 0.82,
    "Investment / Mutual Fund": 0.90,
    "General Banking": 0.75,
}

# These categories NEVER auto-respond — always human review
NEVER_AUTO_RESPOND = {
    "UNAUTHORIZED_TRANSACTION_FRAUD",
    "RECOVERY_AGENT_HARASSMENT",
    "UNSOLICITED_CARD_ISSUANCE",
    "MIS_SELLING_OF_PRODUCTS",
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def _build_system_prompt(
    category: str,
    sentiment: str,
    severity: int,
    urgency_score: float,
    compliance_category: str,
    is_rbi_reportable: bool,
    language: str,
    context_documents: list,
) -> str:
    """
    Build the dynamic system prompt from all upstream agent outputs.
    The prompt changes based on what previous agents detected.
    """

    # Format RAG context as numbered examples
    if context_documents:
        examples_text = "\n\n".join([
            f"EXAMPLE {i + 1} "
            f"[{doc.get('category', 'General')}] "
            f"[Quality: {doc.get('quality_score', 0.5):.1f}] "
            f"[Similarity: {doc.get('similarity', 0):.1%}]:\n"
            f"{doc.get('resolution_text', '')}"
            for i, doc in enumerate(context_documents[:3])
        ])
        context_section = (
            f"SIMILAR PAST RESOLUTIONS (use these as style/tone reference):\n"
            f"{examples_text}\n\n"
        )
    else:
        context_section = (
            "No similar past resolutions available. "
            "Generate a professional response from your training knowledge.\n\n"
        )

    # RBI compliance instruction
    rbi_note = ""
    if is_rbi_reportable:
        rbi_note = (
            f"\n⚠️ RBI COMPLIANCE ALERT: This complaint is categorized as "
            f"{compliance_category} under RBI regulations. "
            f"Do NOT make specific promises about timelines or amounts "
            f"without agent verification. "
            f"Reference the relevant RBI circular in your response.\n"
        )

    # Escalation note for high urgency
    escalation_note = ""
    if urgency_score >= 8:
        escalation_note = (
            "\n⚠️ HIGH URGENCY: Customer is extremely distressed. "
            "Prioritize empathy. Acknowledge their frustration explicitly "
            "before providing resolution steps.\n"
        )

    return f"""You are a senior customer service specialist at an Indian bank.
You are drafting a response to a customer complaint.

COMPLAINT METADATA:
- Category: {category}
- Customer Sentiment: {sentiment}
- Severity: {severity}/5
- Urgency: {urgency_score}/10
- Language: {language}
- RBI Reportable: {'YES' if is_rbi_reportable else 'NO'}
{rbi_note}{escalation_note}
{context_section}

YOUR TASK:
Draft a professional, empathetic, RBI-compliant response.

STRICT OUTPUT FORMAT — respond ONLY with this JSON structure:
{{
  "draft_response": "<professional response to send to the customer>",
  "root_cause": "<one sentence identifying the underlying cause>",
  "action_steps": [
    "<internal action step 1 for the agent to take>",
    "<internal action step 2>",
    "<internal action step 3>"
  ],
  "confidence": <float 0.0-1.0 — how confident you are this resolves the issue>,
  "confidence_reasoning": "<why you assigned this confidence level>"
}}

RULES:
- draft_response: 3-5 sentences, empathetic opening, clear next steps
- root_cause: specific, not generic ("processing error" not "technical issue")
- action_steps: concrete, verifiable by an agent (2-4 steps)
- confidence: lower if complaint is vague or RBI-reportable
- DO NOT include markdown, fences, or text outside the JSON object"""


def generate_resolution(
    complaint_text: str,
    masked_text: str,
    category: str,
    sentiment: str,
    severity: int,
    urgency_score: float,
    compliance_category: str,
    is_rbi_reportable: bool,
    language: str,
    context_documents: list,
) -> dict:
    """
    Generate a resolution draft using GPT-4o with dynamic few-shot prompting.

    Uses masked_text for the system prompt context (safe).
    Uses original complaint_text for the user turn (full context for better response).

    Returns dict with resolution fields and XAI metadata.
    """
    client = _get_client()

    system_prompt = _build_system_prompt(
        category=category,
        sentiment=sentiment,
        severity=severity,
        urgency_score=urgency_score,
        compliance_category=compliance_category,
        is_rbi_reportable=is_rbi_reportable,
        language=language,
        context_documents=context_documents,
    )

    user_message = (
        f"Please generate a resolution for this customer complaint:\n\n"
        f"COMPLAINT: {complaint_text}\n\n"
        f"Remember to respond ONLY with the JSON object."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=800,
    )

    result = json.loads(response.choices[0].message.content)

    draft = result.get("draft_response", "")
    root_cause = result.get("root_cause", "Unable to determine root cause.")
    action_steps = result.get("action_steps", [])
    confidence = float(result.get("confidence", 0.5))
    confidence_reasoning = result.get("confidence_reasoning", "")

    # Get per-category threshold
    category_threshold = CATEGORY_CONFIDENCE_THRESHOLDS.get(category, 0.80)

    # Check if this category is in never-auto-respond list
    never_auto = compliance_category in NEVER_AUTO_RESPOND

    return {
        "draft_response": draft,
        "root_cause": root_cause,
        "action_steps": action_steps,
        "confidence": confidence,
        "confidence_reasoning": confidence_reasoning,
        "category_threshold": category_threshold,
        "meets_threshold": confidence >= category_threshold and not never_auto,
        "never_auto_respond": never_auto,
        "context_used": len(context_documents),
    }