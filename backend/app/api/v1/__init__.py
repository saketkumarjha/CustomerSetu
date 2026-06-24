from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader
from app.api.v1.routes import (
    complaints,
    pipeline,
    explanation,
    rbi,
    feedback,
    dashboard,
    sla,
    agent,
    kb_admin,
    channels,
    debug,
    settings,
    clusters,
    duplicates,
)

# Shared security scheme — makes Swagger show the padlock and documents 401
# on every protected router. Actual enforcement is done by the auth middleware.
# TESTING ONLY — auth disabled; uncomment to re-enable
# _api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
# _PROTECTED = dict(
#     dependencies=[Depends(_api_key_header)],
#     responses={401: {"description": "Unauthorized — missing or invalid X-API-Key header"}},
# )
_PROTECTED = dict()  # no-op while auth is disabled

api_v1_router = APIRouter()

api_v1_router.include_router(
    complaints.router,
    prefix="/complaints",
    tags=["Complaints"],
    **_PROTECTED,
)
api_v1_router.include_router(
    pipeline.router,
    prefix="/pipeline",
    tags=["Pipeline"],
    **_PROTECTED,
)
api_v1_router.include_router(
    explanation.router,
    prefix="/complaints",
    tags=["Explanation (XAI)"],
    **_PROTECTED,
)
api_v1_router.include_router(
    rbi.router,
    prefix="/rbi",
    tags=["RBI Compliance"],
    **_PROTECTED,
)
api_v1_router.include_router(
    feedback.router,
    prefix="/feedback",
    tags=["Feedback"],
    **_PROTECTED,
)
api_v1_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"],
    **_PROTECTED,
)
api_v1_router.include_router(
    sla.router,
    prefix="/sla",
    tags=["SLA Predictor"],
    **_PROTECTED,
)
api_v1_router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent Dashboard"],
    **_PROTECTED,
)
api_v1_router.include_router(
    kb_admin.router,
    prefix="/admin/kb",
    tags=["KB Admin"],
    **_PROTECTED,
)
api_v1_router.include_router(
    channels.demo_router,
    prefix="/channels",
    tags=["Channel Demo"],
    **_PROTECTED,
)
# Webhook routes are called by external services (Twilio) — no API key required
api_v1_router.include_router(
    channels.webhook_router,
    prefix="/channels",
    tags=["Channel Demo"],
)
api_v1_router.include_router(
    debug.router,
    prefix="/debug",
    tags=["Debug"],
    **_PROTECTED,
)
api_v1_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"],
    **_PROTECTED,
)
api_v1_router.include_router(
    clusters.router,
    prefix="/clusters",
    tags=["Incidents"],
    **_PROTECTED,
)
api_v1_router.include_router(
    duplicates.router,
    prefix="/duplicates",
    tags=["Duplicates"],
    **_PROTECTED,
)