from fastapi import FastAPI, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.api.v1 import api_v1_router
from app.middleware.auth import verify_api_key
from app.middleware.rate_limiter import limiter

settings = get_settings()

# Define the security scheme for Swagger UI
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(
    title="Unified Complaint Dashboard API",
    description=(
        "Multi-Agent AI Pipeline for customer complaint processing. "
        "Powered by LangGraph orchestration with real-time SSE streaming, "
        "XAI explainability, and RBI compliance enforcement."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(api_key_header)],
)

# ── Rate limiter setup ────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # tighten to Azure Static Web Apps URL before deploy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth middleware ───────────────────────────────────────────────────────────
app.middleware("http")(verify_api_key)

# ── Versioned API ─────────────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "environment": settings.app_env,
        "api_version": "v2",
        "pipeline": "LangGraph multi-agent",
    }


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Complaint Dashboard API — Multi-Agent Pipeline",
        "docs": "/docs",
        "health": "/health",
    }