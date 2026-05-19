"""
Settings — Runtime toggle for auto-pipeline execution.

GET  /api/v1/settings/auto-mode  → { enabled: bool }
POST /api/v1/settings/auto-mode  → { enabled: bool }

When enabled=False, inbound email and WhatsApp Tier-1+ complaints are
saved + ACK'd but the AI pipeline does NOT run automatically.  Agents
must trigger it manually from the Pipeline tab, exactly like the
Twitter/IVR demo endpoints when auto_run=False.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Module-level flag — shared across all coroutines in the same process.
# Resets to True on backend restart (acceptable for a single-process dev server).
_state: dict = {"auto_pipeline_enabled": True}


def is_auto_pipeline_enabled() -> bool:
    """Called by channel handlers before triggering _trigger_pipeline_bg."""
    return _state["auto_pipeline_enabled"]


class AutoModePayload(BaseModel):
    enabled: bool


@router.get(
    "/auto-mode",
    summary="Get current auto-pipeline mode",
    response_description="Whether the AI pipeline runs automatically for inbound complaints",
)
async def get_auto_mode() -> dict:
    return {"enabled": _state["auto_pipeline_enabled"]}


@router.post(
    "/auto-mode",
    summary="Enable or disable auto-pipeline for all channels",
    response_description="Updated auto-pipeline mode",
)
async def set_auto_mode(body: AutoModePayload) -> dict:
    _state["auto_pipeline_enabled"] = body.enabled
    return {"enabled": _state["auto_pipeline_enabled"]}
