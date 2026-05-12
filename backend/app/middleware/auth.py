from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.config import get_settings

# These paths bypass auth entirely
PUBLIC_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}

# Webhook paths called by external services (Twilio etc.) — no API key
WEBHOOK_PATHS = {"/api/v1/channels/whatsapp/webhook"}


async def verify_api_key(request: Request, call_next):
    """
    API Key Authentication Middleware.

    Reads X-API-Key header and validates against configured key.
    Public paths (health, docs) are whitelisted.

    For POC: single API key.
    For Production: JWT tokens with user roles.
    """
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    # Twilio webhooks don't send API keys — exempt them
    if request.url.path in WEBHOOK_PATHS:
        return await call_next(request)

    settings = get_settings()
    # Support api_key query param for EventSource SSE connections (browsers can't set headers)
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

    if not api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing X-API-Key header."},
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid API key."},
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return await call_next(request)