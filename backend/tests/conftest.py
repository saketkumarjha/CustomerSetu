"""
Pytest + Schemathesis test configuration.

Usage (PowerShell):
    $env:API_KEY = "sk_my_super_secret_key_123"
    pytest tests/ -v

Usage (bash/cmd):
    set API_KEY=sk_my_super_secret_key_123 && pytest tests/ -v

Requirements:
    pip install schemathesis pytest

The API_KEY env var must match the value in .env.
The FastAPI server must be running at APP_URL (default: http://localhost:8000).
"""
import os
import pytest
import schemathesis

APP_URL = os.getenv("APP_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

# Paths called by external services — excluded from auth-required testing.
WEBHOOK_PATHS = {
    "/api/v1/channels/whatsapp/webhook",
    "/api/v1/channels/email/inbound",
}

# Build schema with the X-API-Key header pre-injected so every generated
# request is authenticated. Without this header every protected route returns
# 401 and Schemathesis reports them as failures.
schema = schemathesis.from_uri(
    f"{APP_URL}/openapi.json",
    headers={"X-API-Key": API_KEY},
    # Exclude webhook paths — they are tested separately without the API key.
    endpoint=lambda ep: ep.path not in WEBHOOK_PATHS,
)


@schema.parametrize()
def test_api_schema_compliance(case):
    """
    For every operation in the OpenAPI schema, Schemathesis generates valid
    inputs and asserts that the response matches the documented schema.

    Expected passing status codes: 2xx, 404 (unknown resource IDs), 422
    (validation errors on generated edge-case inputs), 429 (rate limit).
    """
    response = case.call()
    case.validate_response(
        response,
        # All legitimate outcomes for Schemathesis-generated test data:
        #   405 — wrong HTTP method tried on a route (expected, correct behavior)
        #   404 — generated resource IDs don't exist in the test DB
        #   422 — edge-case inputs that fail validation
        #   403 — Twilio signature missing (only in production mode)
        #   429 — rate limiter triggered during rapid runs
        additional_allowed_codes=[403, 404, 405, 422, 429],
    )
