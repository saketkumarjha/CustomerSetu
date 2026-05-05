STRUCTURED_DOC_KEYWORDS = {
    "invoice", "amount", "total", "date", "bill", "receipt",
    "order", "payment", "tax", "gst", "quantity", "price",
    "transaction", "ref", "reference", "due", "balance",
    "debit", "credit", "statement", "charge", "fee"
}

MIN_OCR_TEXT_LENGTH = 50
MIN_KEYWORD_MATCHES = 2


def classify_image(ocr_text: str) -> str:
    """
    Given OCR output from an image, decide which extraction strategy applies.

    Returns:
        "ocr"    — image is a structured document, use OCR text as-is
        "vision" — image is a photo/screenshot, use GPT-4o Vision instead

    Decision logic:
        If OCR produced substantial text AND that text contains at least 2
        structured-document keywords → it is a structured doc → trust the OCR.
        Otherwise → it is a photo/screenshot → send to GPT-4o Vision.

    Why this order: we always run OCR first (fast, free, local) and only
    fall back to Vision (slower, costs tokens) when OCR is insufficient.
    """
    if len(ocr_text) < MIN_OCR_TEXT_LENGTH:
        return "vision"

    text_lower = ocr_text.lower()
    keyword_matches = sum(1 for kw in STRUCTURED_DOC_KEYWORDS if kw in text_lower)

    if keyword_matches >= MIN_KEYWORD_MATCHES:
        return "ocr"

    return "vision"