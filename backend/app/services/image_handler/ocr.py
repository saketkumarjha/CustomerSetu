import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from app.core.config import get_settings


def _configure_tesseract() -> None:
    """Set Tesseract binary path from config. Called once per process."""
    settings = get_settings()
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    Preprocess image to improve OCR accuracy.
    Grayscale + sharpen + contrast boost are the three steps that
    make the biggest difference on photos of documents.
    """
    img = img.convert("L")                      # grayscale
    img = img.filter(ImageFilter.SHARPEN)        # sharpen edges
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)                  # boost contrast
    return img


def extract_text_with_ocr(image_bytes: bytes) -> str:
    """
    Run Tesseract OCR on image bytes.
    Returns the extracted text string (may be empty if image has no text).
    """
    _configure_tesseract()
    img = Image.open(io.BytesIO(image_bytes))
    processed = _preprocess_image(img)
    text = pytesseract.image_to_string(processed)
    return text.strip()