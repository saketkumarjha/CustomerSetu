from app.services.image_handler.storage import upload_image_to_storage
from app.services.image_handler.ocr import extract_text_with_ocr
from app.services.image_handler.vision import describe_image_with_vision
from app.services.image_handler.classifier import classify_image
from app.services.image_handler.merger import merge_texts


def process_image_attachment(
    file_bytes: bytes,
    filename: str,
    complaint_text: str
) -> dict:
    """
    Full image processing pipeline for one attachment.

    Steps:
    1. Upload original image to Supabase Storage → get URL
    2. Run OCR on image (fast, free, local)
    3. Classify: is this a structured doc or a photo?
    4. If structured doc → use OCR text
       If photo/screenshot → run GPT-4o Vision → use description
    5. Merge image text with complaint text
    6. Return everything the route needs to build its response

    This function is the ONLY thing the outside world calls.
    All internal steps are invisible to the caller.
    """
    # Step 1: Upload to storage first — we want the URL regardless of method
    image_url = upload_image_to_storage(file_bytes, filename)

    # Step 2: Always run OCR first — it is fast and free
    ocr_text = extract_text_with_ocr(file_bytes)

    # Step 3: Decide which result to use
    method = classify_image(ocr_text)

    # Step 4: Get final image text based on classification
    if method == "ocr":
        image_text = ocr_text
    else:
        image_text = describe_image_with_vision(file_bytes)

    # Step 5: Merge with complaint text
    merged = merge_texts(complaint_text, image_text, method)

    return {
        "image_url": image_url,
        "extraction_method": method,
        "extracted_image_text": image_text,
        "merged_text": merged
    }