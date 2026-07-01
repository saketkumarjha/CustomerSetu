# CRE Standalone — Customer Requirement Engine

Drop-in **Customer Requirement Engine** for CustomerSetu. Validates complaint adequacy **before** the main LangGraph AI pipeline runs.

**All switches are OFF by default** — copy this folder in, wire when ready; existing pipeline behaviour is unchanged until you enable CRE.

---

## What it does

| Tier | Technology | Purpose | Default |
|------|------------|---------|---------|
| **L0** | Keyword rules (`master.json`) | Block spam, fast-path FAQs, escalate txn/fraud keywords | On when CRE enabled |
| **L1** | Regex + category bundles | Detect category, extract txn ID, date, amount, CIF, etc. | On when CRE enabled |
| **L2** | GPT-4o-mini | Extract fields from free text + compose gap message | **Off** |
| **L3** | GPT-4o-mini | Multi-turn conversational gap-fill on follow-ups | **Off** |

```
Customer message
       │
       ▼
  CRE_ENABLED? ──no──► pass-through (adequate=true, pipeline unchanged)
       │ yes
       ▼
  L0 → L1 → L2? → L3? (follow-ups only)
       │
       ├── adequate ──► promote to CMP / run pipeline
       └── inadequate ──► TMP session + gap message
```

---

## Folder layout

```
cre_standalone/
├── README.md                 ← you are here
├── requirements.txt          ← openai (only for L2/L3)
├── cre_config.py             ← all feature flags (default OFF)
├── config_loader.py          ← reads master.json
├── master.json               ← L0/L1 rules (single source of truth)
├── orchestrator.py           ← L0→L1→L2→L3 pipeline + intake/followup
├── tiers/
│   ├── l0_rules.py
│   ├── l1_regex.py
│   ├── l2_mini_llm.py
│   └── l3_conversational.py
├── session/
│   └── memory_store.py       ← in-memory TMP sessions (swap for Redis in prod)
├── adapters/
│   └── customersetu.py       ← thin bridge to CustomerSetu backend
└── tests/
    └── test_cre_standalone.py
```

**No imports from `app.*` inside core modules** — only `adapters/customersetu.py` optionally reads CustomerSetu settings.

---

## Quick start (standalone, no server)

From the repo root (`CustomerSetu-main/`):

```bash
cd CustomerSetu-main
python -m pytest cre_standalone/tests/ -v
```

Try it in Python:

```python
import sys
sys.path.insert(0, ".")  # repo root

from cre_standalone import CreConfig, evaluate_cre, intake, evaluate_followup

# CRE off — always passes (safe default)
r = evaluate_cre("hi", config=CreConfig(enabled=False))
print(r["adequate"])  # True, status=skipped

# CRE on — L0 + L1 only (no LLM cost)
cfg = CreConfig(enabled=True, l2_enabled=False, l3_enabled=False)
r = evaluate_cre(
    "Rs 5000 debited on 15/01/2026 UTR 123456789012 CIF 9988776",
    contact="9876543210",
    name="Rahul",
    config=cfg,
)
print(r["tier_used"], r["adequate"], r["extracted_fields"])

# Intake with TMP session when inadequate
r = intake("My card was stolen", contact="9876543210", config=cfg)
print(r["session_id"], r["gap_message"])

# Follow-up turn (L3 runs if CRE_L3_ENABLED=true)
if r["session_id"]:
    r2 = evaluate_followup(
        r["session_id"],
        "Debit card ending 4521, txn on 20/01/2026 amount Rs 2500",
        config=cfg,
    )
    print(r2["adequate"], r2.get("missing_fields"))
```

---

## Environment variables

All default to **off** / empty:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRE_ENABLED` | `false` | Master switch |
| `CRE_L0_ENABLED` | `true` | Keyword gate (when CRE on) |
| `CRE_L1_ENABLED` | `true` | Regex extraction (when CRE on) |
| `CRE_L2_ENABLED` | `false` | GPT-4o-mini extraction |
| `CRE_L3_ENABLED` | `false` | Multi-turn conversational agent |
| `CRE_BLOCK_PIPELINE_IF_INADEQUATE` | `false` | Hard 409 gate on `POST /pipeline/run` |
| `CRE_L2_MODEL` | `gpt-4o-mini` | L2 model |
| `CRE_L3_MODEL` | `gpt-4o-mini` | L3 model |
| `CRE_L3_MAX_TURNS` | `5` | Max follow-up turns before giving up |
| `CRE_DRAFT_EXPIRY_DAYS` | `7` | Session TTL hint |
| `OPENAI_API_KEY` | — | Required only when L2 or L3 enabled |

---

## Plug into CustomerSetu (3 steps)

### 1. Copy folder

Copy `cre_standalone/` into your repo root (already there if you cloned this branch).

Ensure Python can import it — add repo root to `PYTHONPATH` or run uvicorn from repo root:

```bash
# backend/.env
CRE_ENABLED=true
CRE_L2_ENABLED=false
CRE_L3_ENABLED=false
```

### 2. Swap orchestrator import (optional)

In `backend/app/api/v1/routes/cre.py`, replace:

```python
from app.services.cre.orchestrator import evaluate_cre
```

with:

```python
from cre_standalone.adapters.customersetu import evaluate_for_app as evaluate_cre
```

Same for `backend/app/api/v1/routes/pipeline.py` optional gate.

The adapter reads `CRE_*` env vars **or** falls back to `app.core.config.Settings` if present.

### 3. Run migration (if using Supabase drafts)

The built-in CustomerSetu CRE routes use `complaint_drafts` in Supabase. The standalone package uses **in-memory sessions** by default. For production:

- Keep using Supabase via existing `draft_service.py`, **or**
- Replace `MemorySessionStore` with Redis in `session/memory_store.py`

---

## API surface (library)

| Function | Description |
|----------|-------------|
| `evaluate_cre(text, config=...)` | Stateless first-pass check |
| `intake(text, config=...)` | Evaluate + create TMP session if inadequate |
| `evaluate_followup(session_id, extra_text, config=...)` | Multi-turn gap fill |
| `get_session(session_id)` | Fetch session state |

All return a dict with at least:

```python
{
    "adequate": bool,
    "status": "skipped" | "adequate" | "awaiting_info" | "rejected",
    "tier_used": "L0" | "L1" | "L2" | "L3" | None,
    "category": str | None,
    "extracted_fields": dict,
    "missing_fields": list,
    "gap_message": str | None,
}
```

---

## Customising rules

Edit `master.json` only — no code changes needed for:

- L0 block/allow/escalate keywords
- L1 category bundles
- Required fields per category (`category_requirements`)
- Regex extractors (`regex_extractors`)

Point to a custom file:

```python
from cre_standalone.config_loader import set_master_path
set_master_path("/path/to/my_master.json")
```

Or set env `CRE_MASTER_JSON=/path/to/my_master.json`.

---

## L2 vs L3 — when to enable

| Enable | When |
|--------|------|
| **L2** | Customers write long free-text complaints; regex misses fields often |
| **L3** | WhatsApp/email multi-turn — customer replies in chunks over several messages |

Start with **L0 + L1 only** (no API cost). Enable L2/L3 in staging first.

---

## Tests

```bash
# From repo root
python -m pytest cre_standalone/tests/ -v
```

Tests cover: disabled pass-through, L0/L1 adequacy, gap messages, intake sessions, follow-up turns, L2 gate.

---

## Relationship to `backend/app/services/cre/`

CustomerSetu already has an integrated CRE under `backend/app/services/cre/`. This **`cre_standalone/`** folder is a **separate, portable copy** you can:

- Drop into other projects
- Commit independently
- Enable without touching LangGraph

When both exist, prefer **one** orchestrator via the adapter — do not call both.

---

## License

Same as CustomerSetu parent project.
