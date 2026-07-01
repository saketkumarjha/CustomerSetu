"""
CRE orchestrator — L0 → L1 → L2 (optional) → L3 (optional on follow-ups).

When config.enabled=False, returns a pass-through result immediately.
"""

from __future__ import annotations

from typing import Any

from cre_standalone.config_loader import field_label
from cre_standalone.cre_config import CreConfig, DEFAULT_CONFIG
from cre_standalone.session.memory_store import CreSession, MemorySessionStore, default_store
from cre_standalone.tiers.l0_rules import run_l0
from cre_standalone.tiers.l1_regex import run_l1
from cre_standalone.tiers.l2_mini_llm import run_l2
from cre_standalone.tiers.l3_conversational import run_l3


def _pass_through() -> dict[str, Any]:
    return {
        "adequate": True,
        "status": "skipped",
        "tier_used": None,
        "category": None,
        "extracted_fields": {},
        "field_confidence": {},
        "missing_fields": [],
        "missing_field_labels": [],
        "reason": "CRE disabled — pass-through.",
        "gap_message": None,
    }


def _build_response(step: dict[str, Any]) -> dict[str, Any]:
    action = step.get("action")
    adequate = action == "adequate"
    missing = step.get("missing_fields") or []
    missing_labels = step.get("missing_field_labels") or [field_label(f) for f in missing]
    gap = step.get("gap_message") or _gap_message(missing_labels, step.get("category"))

    return {
        "adequate": adequate,
        "status": "adequate" if adequate else ("rejected" if action == "rejected" else "awaiting_info"),
        "tier_used": step.get("tier_used"),
        "category": step.get("category"),
        "extracted_fields": step.get("extracted_fields") or {},
        "field_confidence": step.get("field_confidence") or {},
        "missing_fields": missing,
        "missing_field_labels": missing_labels,
        "reason": step.get("reason", ""),
        "gap_message": gap,
    }


def _gap_message(missing_labels: list[str], category: str | None) -> str | None:
    if not missing_labels:
        return None
    prefix = f"For your {category} request, please provide:" if category else "Please provide:"
    items = "\n".join(f"  \u2022 {label}" for label in missing_labels)
    return f"{prefix}\n{items}"


def _run_pipeline(
    message_text: str,
    *,
    config: CreConfig,
    contact: str | None = None,
    name: str | None = None,
    session_id: str | None = None,
    use_l3: bool = False,
    prior_extracted: dict[str, str] | None = None,
    prior_category: str | None = None,
    prior_missing: list[str] | None = None,
    turn_count: int = 0,
    merged_text: str | None = None,
) -> dict[str, Any]:
    """Core tier chain."""
    if config.l0_enabled:
        l0 = run_l0(message_text, contact=contact, name=name)
        if l0["action"] in ("rejected", "adequate", "awaiting_info"):
            return _build_response(l0)
    else:
        l0 = {"action": "pass_l1"}

    if not config.l1_enabled:
        return _pass_through()

    l1 = run_l1(message_text, contact=contact, name=name)
    if l1["action"] in ("rejected", "adequate"):
        return _build_response(l1)

    # Merge prior extracted fields from session (follow-up turns)
    if prior_extracted:
        merged_fields = {**prior_extracted, **l1.get("extracted_fields", {})}
        l1["extracted_fields"] = merged_fields
        merged_conf = {**l1.get("field_confidence", {})}
        for k in prior_extracted:
            merged_conf.setdefault(k, 0.85)
        l1["field_confidence"] = merged_conf
        category = prior_category or l1.get("category")
        if category:
            from cre_standalone.config_loader import category_requirements
            l1["missing_fields"] = [
                f for f in category_requirements(category)
                if f not in merged_fields
            ]
            l1["missing_field_labels"] = [field_label(f) for f in l1["missing_fields"]]
            l1["category"] = category
            if not l1["missing_fields"]:
                l1["action"] = "adequate"

    if l1["action"] == "adequate":
        return _build_response(l1)

    # L2
    if config.l2_enabled:
        l2 = run_l2(
            message_text,
            config=config,
            contact=contact,
            name=name,
            missing_from_l1=l1.get("missing_fields"),
            category_from_l1=l1.get("category"),
            session_id=session_id,
        )
        if l2["action"] == "adequate":
            return _build_response(l2)
        step = l2
    else:
        step = l1

    # L3 — only on follow-up turns or when explicitly requested
    if use_l3 and config.l3_enabled and step.get("action") == "awaiting_info":
        l3 = run_l3(
            config=config,
            latest_message=message_text,
            merged_text=merged_text or message_text,
            category=step.get("category") or prior_category or "General Banking",
            extracted_so_far=step.get("extracted_fields") or prior_extracted or {},
            missing_fields=step.get("missing_fields") or prior_missing or [],
            turn_count=turn_count,
            session_id=session_id,
            contact=contact,
            name=name,
        )
        return _build_response(l3)

    return _build_response(step)


def evaluate_cre(
    message_text: str,
    *,
    contact: str | None = None,
    name: str | None = None,
    session_id: str | None = None,
    config: CreConfig | None = None,
) -> dict[str, Any]:
    """
    Stateless first-pass evaluation (L0 → L1 → optional L2).

    When config.enabled=False, returns pass-through (adequate=True).
    """
    cfg = config or DEFAULT_CONFIG
    if not cfg.enabled:
        return _pass_through()

    return _run_pipeline(
        message_text,
        config=cfg,
        contact=contact,
        name=name,
        session_id=session_id,
        use_l3=False,
    )


def evaluate_followup(
    session_id: str,
    extra_text: str,
    *,
    store: MemorySessionStore | None = None,
    config: CreConfig | None = None,
) -> dict[str, Any]:
    """
    Multi-turn follow-up — re-runs L1 on combined text, then L2/L3 if enabled.

    Returns dict with session_id and updated session fields.
    """
    cfg = config or DEFAULT_CONFIG
    if not cfg.enabled:
        return {**_pass_through(), "session_id": session_id}

    mem = store or default_store
    session = mem.get(session_id)
    if not session:
        return {
            "adequate": False,
            "status": "not_found",
            "session_id": session_id,
            "reason": f"Session {session_id} not found or expired.",
            "gap_message": None,
        }

    session.merged_text = session.merged_text + "\n\n[Follow-up]: " + extra_text.strip()
    session.turn_count += 1

    result = _run_pipeline(
        session.merged_text,
        config=cfg,
        contact=session.contact,
        name=session.name,
        session_id=session_id,
        use_l3=cfg.l3_enabled,
        prior_extracted=session.extracted_fields,
        prior_category=session.category,
        prior_missing=session.missing_fields,
        turn_count=session.turn_count,
        merged_text=session.merged_text,
    )

    # Also run L3 on first follow-up if L3 enabled and still awaiting
    if (
        cfg.l3_enabled
        and not result["adequate"]
        and result.get("tier_used") != "L3"
    ):
        l3 = run_l3(
            config=cfg,
            latest_message=extra_text,
            merged_text=session.merged_text,
            category=result.get("category") or session.category or "General Banking",
            extracted_so_far={**session.extracted_fields, **result.get("extracted_fields", {})},
            missing_fields=result.get("missing_fields") or [],
            turn_count=session.turn_count,
            session_id=session_id,
            contact=session.contact,
            name=session.name,
        )
        result = _build_response(l3)

    session.extracted_fields = {
        **session.extracted_fields,
        **result.get("extracted_fields", {}),
    }
    session.field_confidence = {
        **session.field_confidence,
        **result.get("field_confidence", {}),
    }
    session.missing_fields = result.get("missing_fields") or []
    session.missing_field_labels = result.get("missing_field_labels") or []
    session.gap_message = result.get("gap_message")
    session.category = result.get("category") or session.category
    session.tier_used = result.get("tier_used")
    session.cre_status = "adequate" if result["adequate"] else (
        "rejected" if result.get("status") == "rejected" else "awaiting_info"
    )
    mem.save(session)

    return {**result, "session_id": session_id, "turn_count": session.turn_count}


def intake(
    message_text: str,
    *,
    contact: str | None = None,
    name: str | None = None,
    store: MemorySessionStore | None = None,
    config: CreConfig | None = None,
) -> dict[str, Any]:
    """
    First message intake — evaluate and create TMP session if inadequate.
    """
    cfg = config or DEFAULT_CONFIG
    if not cfg.enabled:
        return {**_pass_through(), "session_id": None}

    result = evaluate_cre(message_text, contact=contact, name=name, config=cfg)

    if result["adequate"] or result.get("status") == "rejected":
        return {**result, "session_id": None}

    mem = store or default_store
    session = mem.create(original_text=message_text.strip(), contact=contact, name=name)
    session.extracted_fields = result.get("extracted_fields") or {}
    session.field_confidence = result.get("field_confidence") or {}
    session.missing_fields = result.get("missing_fields") or []
    session.missing_field_labels = result.get("missing_field_labels") or []
    session.gap_message = result.get("gap_message")
    session.category = result.get("category")
    session.tier_used = result.get("tier_used")
    session.cre_status = "awaiting_info"
    mem.save(session)

    return {
        **result,
        "session_id": session.session_id,
        "draft_link": f"/draft/{session.session_id}",
    }


def get_session(session_id: str, store: MemorySessionStore | None = None) -> CreSession | None:
    mem = store or default_store
    return mem.get(session_id)
