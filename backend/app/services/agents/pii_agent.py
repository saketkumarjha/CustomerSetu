"""
PII Agent — Microsoft Presidio Implementation

Responsibilities:
1. Detect all PII entities in merged_text (complaint + image text)
2. Mask detected entities with type-specific placeholders
3. Detect language of the complaint
4. Build PII audit log (entity types + positions, NOT values)
5. Return masked_text safe for all downstream agents

Indian PII Recognizers (custom):
- IN_AADHAAR: 12-digit format (XXXX XXXX XXXX), first digit 2-9
- IN_PAN: 5 letters + 4 digits + 1 letter (ABCDE1234F)
- IN_PHONE: 10 digits starting with 6-9, optional +91/0 prefix

Data flow rule enforced here:
  masked_text  → flows to ALL downstream agents (Duplicate, Fan-out, RAG, Resolution)
  original_text → stored in Supabase complaints table only, never forwarded
"""

import time
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine
from langdetect import detect, LangDetectException

# ── Singleton engines — loaded once at module import ──────────────────────────
# Loading spaCy model takes 2-3 seconds. Module-level singleton
# ensures this cost is paid once at startup, not per request.

_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None


def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """
    Lazy-initialise Presidio engines on first call.
    All subsequent calls reuse the same instances.
    """
    global _analyzer, _anonymizer

    if _analyzer is None:
        _analyzer = AnalyzerEngine()

        # ── Custom Indian PII recognizers ─────────────────────────────────

        # Aadhaar: 12 digits in 4-4-4 format, first digit always 2-9
        # Example: 2345 6789 0123
        aadhaar_recognizer = PatternRecognizer(
            supported_entity="IN_AADHAAR",
            patterns=[
                Pattern(
                    name="aadhaar_spaced",
                    regex=r"\b[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}\b",
                    score=0.95,
                ),
                Pattern(
                    name="aadhaar_unspaced",
                    regex=r"\b[2-9]{1}[0-9]{11}\b",
                    score=0.75,
                ),
            ],
        )

        # PAN: AAAAA9999A format — 5 uppercase letters, 4 digits, 1 uppercase letter
        # Example: ABCDE1234F
        pan_recognizer = PatternRecognizer(
            supported_entity="IN_PAN",
            patterns=[
                Pattern(
                    name="pan_card",
                    regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
                    score=0.95,
                )
            ],
        )

        # Indian mobile: 10 digits starting with 6-9, optional +91 or 0 prefix
        # Matches: 9876543210 | +919876543210 | 09876543210
        in_phone_recognizer = PatternRecognizer(
            supported_entity="IN_PHONE",
            patterns=[
                Pattern(
                    name="indian_mobile",
                    regex=r"\b(\+91|0)?[6-9]\d{9}\b",
                    score=0.85,
                )
            ],
        )

        # Register all custom recognizers
        _analyzer.registry.add_recognizer(aadhaar_recognizer)
        _analyzer.registry.add_recognizer(pan_recognizer)
        _analyzer.registry.add_recognizer(in_phone_recognizer)

    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()

    return _analyzer, _anonymizer


# ── Entity list — what Presidio scans for ────────────────────────────────────
# These are checked on every analyze() call.
# Adding a new entity here is the only change needed to detect new PII types.

ENTITIES_TO_DETECT = [
    "PERSON",           # Full names
    "EMAIL_ADDRESS",    # email@domain.com
    "PHONE_NUMBER",     # Generic international phone
    "CREDIT_CARD",      # 16-digit card numbers
    "IBAN_CODE",        # Bank account IBANs
    "IP_ADDRESS",       # IP addresses
    "IN_AADHAAR",       # Indian Aadhaar (custom)
    "IN_PAN",           # Indian PAN card (custom)
    "IN_PHONE",         # Indian mobile number (custom)
]


def run_pii_detection(text: str) -> dict:
    """
    Full PII detection and masking pipeline.

    Args:
        text: The merged complaint text (complaint + image text)

    Returns dict with:
        masked_text:     PII replaced with <ENTITY_TYPE> placeholders
        language:        Detected language code (en, hi, ta, etc.)
        pii_entities:    List of dicts — entity type, position, confidence
                         (NO actual PII values stored here)
        pii_detected:    Boolean — was any PII found?
        entity_summary:  Dict of entity_type → count (for XAI reasoning)

    Raises:
        Exception if Presidio fails — caller handles gracefully
    """
    analyzer, anonymizer = _get_engines()

    # ── Step 1: Detect PII entities ───────────────────────────────────────
    analysis_results = analyzer.analyze(
        text=text,
        entities=ENTITIES_TO_DETECT,
        language="en",
    )

    # ── Step 2: Anonymize — replace with type-specific placeholders ───────
    # Using entity type as the replacement (not a generic <REDACTED>) so that
    # downstream LLMs understand what was masked and can still reason about context.
    # e.g. "My name is <PERSON> and my card number is <CREDIT_CARD>"
    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=analysis_results,
    )
    masked_text = anonymized.text

    # ── Step 3: Detect language ───────────────────────────────────────────
    try:
        language = detect(text)
    except LangDetectException:
        language = "en"  # default if detection fails

    # ── Step 4: Build audit log — positions and types only, NEVER values ──
    # This is the compliance audit trail. It answers "what PII was present?"
    # without recording "what were those values?"
    pii_entities = [
        {
            "entity_type": result.entity_type,
            "start": result.start,
            "end": result.end,
            "confidence": round(result.score, 3),
        }
        for result in analysis_results
    ]

    # ── Step 5: Build entity summary for XAI reasoning ───────────────────
    entity_summary: dict[str, int] = {}
    for entity in pii_entities:
        entity_type = entity["entity_type"]
        entity_summary[entity_type] = entity_summary.get(entity_type, 0) + 1

    return {
        "masked_text": masked_text,
        "language": language,
        "pii_entities": pii_entities,
        "pii_detected": len(pii_entities) > 0,
        "entity_summary": entity_summary,
    }


def build_pii_reasoning(result: dict) -> str:
    """
    Build human-readable XAI reasoning string from PII detection result.
    This is what your frontend displays in the agent step detail.
    """
    if not result["pii_detected"]:
        return (
            f"No PII entities detected in complaint text. "
            f"Text is safe to process by all downstream agents. "
            f"Language detected: {result['language'].upper()}."
        )

    entity_lines = []
    for entity_type, count in result["entity_summary"].items():
        entity_lines.append(f"  • {entity_type}: {count} instance(s) found and masked")

    entities_text = "\n".join(entity_lines)
    total = len(result["pii_entities"])

    return (
        f"PII Detection Complete — {total} entity instance(s) found and masked.\n"
        f"Entities detected:\n{entities_text}\n"
        f"All PII replaced with <ENTITY_TYPE> placeholders.\n"
        f"Masked text is safe for Groq API, embeddings, and storage.\n"
        f"Language detected: {result['language'].upper()}.\n"
        f"Original text stored encrypted in Supabase only."
    )