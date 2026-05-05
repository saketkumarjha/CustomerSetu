def merge_texts(complaint_text: str, image_text: str, method: str) -> str:
    """
    Merge the original complaint text with image-extracted content.

    Args:
        complaint_text: The customer's typed complaint
        image_text:     Text extracted from image (OCR or Vision)
        method:         "ocr" or "vision" — used for the label

    Returns:
        A single merged string with clear section labels.

    Why labels matter: when this merged text reaches the resolution generator
    on Day 10, the LLM needs to understand which part is the customer's own
    words and which part is evidence from an attachment. Without labels,
    the LLM treats it as one block and may misattribute details.
    """
    method_label = (
        "Document text (extracted by OCR)"
        if method == "ocr"
        else "Image description (analysed by GPT-4o Vision)"
    )

    return (
        f"[Customer complaint]\n"
        f"{complaint_text.strip()}\n\n"
        f"[{method_label}]\n"
        f"{image_text.strip()}"
    )