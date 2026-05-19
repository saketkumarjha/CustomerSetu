import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.datastructures import MutableHeaders
from starlette.routing import Match
from app.core.config import get_settings
from app.api.v1 import api_v1_router
from app.middleware.auth import verify_api_key
from app.middleware.rate_limiter import limiter
settings = get_settings()
_ROUTE_QUERY_PARAMS: list[tuple[str, re.Pattern, set[str]]] = []
@asynccontextmanager
async def lifespan(app: FastAPI):
    schema = app.openapi()
    for path, path_item in schema.get("paths", {}).items():
        regex_str = "^" + re.sub(r"\{[^}]+\}", "[^/]+", path).rstrip("/") + r"/?$"
        pattern = re.compile(regex_str)
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            valid = {
                p["name"]
                for p in operation.get("parameters", [])
                if p.get("in") == "query"
            }
            _ROUTE_QUERY_PARAMS.append((method.upper(), pattern, valid))
    yield
    # shutdown: nothing to clean up
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
    lifespan=lifespan,
)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 as JSON {"detail": "..."} matching the rest of the API's error format."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Please retry after the window resets."},
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
class _AllowHeaderMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def patched_send(message):
            if message["type"] == "http.response.start" and message.get("status") == 405:
                fastapi_app = scope.get("app")
                allowed: set[str] = set()
                if fastapi_app and hasattr(fastapi_app, "routes"):
                    for route in fastapi_app.routes:
                        try:
                            match, _ = route.matches(scope)
                        except Exception:
                            continue
                        if match == Match.PARTIAL:
                            if hasattr(route, "methods") and route.methods:
                                allowed.update(m.upper() for m in route.methods)
                if allowed:
                    if "GET" in allowed:
                        allowed.add("HEAD")
                    allowed.add("OPTIONS")
                    headers = MutableHeaders(scope=message)
                    headers["Allow"] = ", ".join(sorted(allowed))
            await send(message)

        await self.app(scope, receive, patched_send)


# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"] is incompatible with allow_credentials=True (CORS spec + Starlette 0.20+).
    # Use explicit origins in production. For local dev the wildcard pattern below works.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth middleware ───────────────────────────────────────────────────────────
# TESTING ONLY — uncomment to re-enable API key auth
# app.middleware("http")(verify_api_key)

app.add_middleware(_AllowHeaderMiddleware)


# ── Unknown-query-param rejection middleware ──────────────────────────────────
@app.middleware("http")
async def reject_unknown_query_params(request: Request, call_next):
    if request.query_params and _ROUTE_QUERY_PARAMS:
        method = request.method
        path = request.url.path.rstrip("/") or "/"
        for route_method, pattern, valid_params in _ROUTE_QUERY_PARAMS:
            if route_method == method and pattern.match(path):
                unknown = set(request.query_params.keys()) - valid_params
                if unknown:
                    # Return 422 with HTTPValidationError array format — FastAPI
                    # documents 422 on every route, so this is never "undocumented".
                    return JSONResponse(
                        status_code=422,
                        content={
                            "detail": [
                                {
                                    "type": "extra_forbidden",
                                    "loc": ["query", param],
                                    "msg": "Extra inputs are not permitted",
                                    "input": request.query_params.get(param),
                                }
                                for param in sorted(unknown)
                            ]
                        },
                    )
                break
    return await call_next(request)


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
