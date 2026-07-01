"""
CRE configuration — all switches OFF by default.

When ``enabled=False``, the orchestrator returns a pass-through result and
never calls L0–L3.  The main CustomerSetu pipeline is unaffected.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class CreConfig:
    # Master switch
    enabled: bool = False

    # Tier switches (only evaluated when enabled=True)
    l0_enabled: bool = True
    l1_enabled: bool = True
    l2_enabled: bool = False
    l3_enabled: bool = False

    # Optional hard gate on downstream pipeline
    block_pipeline_if_inadequate: bool = False

    # LLM tiers (L2/L3)
    openai_api_key: str = ""
    l2_model: str = "gpt-4o-mini"
    l3_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 20.0

    # Multi-turn L3
    l3_max_turns: int = 5

    # Draft / session TTL
    draft_expiry_days: int = 7
    session_ttl_seconds: int = 604800  # 7 days

    # Path override for master.json (None = bundled default)
    master_json_path: str | None = None

    @classmethod
    def from_env(cls) -> CreConfig:
        return cls(
            enabled=_env_bool("CRE_ENABLED", False),
            l0_enabled=_env_bool("CRE_L0_ENABLED", True),
            l1_enabled=_env_bool("CRE_L1_ENABLED", True),
            l2_enabled=_env_bool("CRE_L2_ENABLED", False),
            l3_enabled=_env_bool("CRE_L3_ENABLED", False),
            block_pipeline_if_inadequate=_env_bool("CRE_BLOCK_PIPELINE_IF_INADEQUATE", False),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            l2_model=os.environ.get("CRE_L2_MODEL", "gpt-4o-mini"),
            l3_model=os.environ.get("CRE_L3_MODEL", "gpt-4o-mini"),
            l3_max_turns=int(os.environ.get("CRE_L3_MAX_TURNS", "5")),
            draft_expiry_days=int(os.environ.get("CRE_DRAFT_EXPIRY_DAYS", "7")),
            master_json_path=os.environ.get("CRE_MASTER_JSON") or None,
        )


# Module-level default — always off until caller overrides or loads from env
DEFAULT_CONFIG = CreConfig()
