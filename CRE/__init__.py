"""
Customer Requirement Engine (CRE) — standalone drop-in package.

L0 keyword rules → L1 regex extraction → L2 mini-LLM → L3 conversational follow-up.

All tiers are OFF by default (master switch CRE_ENABLED=false).
"""

from cre_standalone.cre_config import CreConfig, DEFAULT_CONFIG
from cre_standalone.orchestrator import (
    evaluate_cre,
    evaluate_followup,
    get_session,
    intake,
)

__all__ = [
    "CreConfig",
    "DEFAULT_CONFIG",
    "evaluate_cre",
    "evaluate_followup",
    "get_session",
    "intake",
]

__version__ = "1.0.0"
