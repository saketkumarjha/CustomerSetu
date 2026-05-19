from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from app.core.config import get_settings

# These paths bypass auth entirely
PUBLIC_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}

# Webhook paths called by external services (Twilio, email poller) — no API key
WEBHOOK_PATHS = {
    "/api/v1/channels/whatsapp/webhook",
    "/api/v1/channels/email/inbound",
}

# Methods not declared in any route — must return 405 before auth runs so that
# Schemathesis / security scanners see the correct status code.
# TRACE is also blocked to prevent Cross-Site Tracing (XST) attacks.
_UNSUPPORTED_METHODS = frozenset({"TRACE", "CONNECT"})


async def verify_api_key(request: Request, call_next):
    if request.method in _UNSUPPORTED_METHODS:
        return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

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