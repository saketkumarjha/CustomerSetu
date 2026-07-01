"""Load CRE rules from master.json (single source of truth)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_MASTER = Path(__file__).resolve().parent / "master.json"
_override_path: Path | None = None


def set_master_path(path: str | Path | None) -> None:
    """Point config loader at a custom master.json (clears cache)."""
    global _override_path
    _override_path = Path(path) if path else None
    load_master.cache_clear()


def _master_path() -> Path:
    return _override_path or _DEFAULT_MASTER


@lru_cache(maxsize=1)
def load_master() -> dict[str, Any]:
    with open(_master_path(), encoding="utf-8") as f:
        return json.load(f)


def get_settings() -> dict[str, Any]:
    return load_master().get("settings", {})


def get_l0() -> dict[str, Any]:
    return load_master().get("l0", {})


def get_l1() -> dict[str, Any]:
    return load_master().get("l1", {})


def default_category() -> str:
    return get_settings().get("default_category", "General Banking")


def field_label(key: str) -> str:
    return get_l1().get("field_labels", {}).get(key, key.replace("_", " ").title())


def category_requirements(category: str) -> list[str]:
    reqs = get_l1().get("category_requirements", {})
    return reqs.get(category, reqs.get(default_category(), ["name", "contact", "description"]))
