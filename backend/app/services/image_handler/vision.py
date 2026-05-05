import base64
import httpx
from openai import OpenAI
from app.core.config import get_settings

_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    """Singleton OpenAI client."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


VISION_PROMPT = """You are a customer complaint analyst reviewing image evidence 
submitted with a complaint.

Describe what you see in this image with focus on:
- Any visible damage, defects, or quality issues
- Wrong or missing items
- Delivery or packaging condition
- Any text, numbers, or labels that are relevant to a complaint
- Any evidence of incorrect charges, billing discrepancies, or 
  transaction errors

Be specific and factual. Do not speculate. Do not include information 
that is not visible in the image. Keep your description under 200 words."""


def describe_image_with_gemini(image_bytes: bytes) -> str:
    """Fallback to Gemini Flash API."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": VISION_PROMPT
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ]
    }
    
    settings = get_settings()
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": settings.gemini_api_key
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"Gemini fallback also failed: {e}")
        return "Image description unavailable due to AI service errors."


def describe_image_with_vision(image_bytes: bytes) -> str:
    """
    Send image to GPT-4o Vision and get a complaint-relevant description.
    Returns description string.
    """
    client = _get_openai_client()
    settings = get_settings()

    # Encode image as base64 for the API
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model=settings.openai_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                                "detail": "high"
                            }
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API failed: {e}. Falling back to Gemini...")
        return describe_image_with_gemini(image_bytes)