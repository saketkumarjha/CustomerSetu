# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Running the Project

### Backend
```bash
cd backend
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac
pip install -r requirements.txt
python -m spacy download en_core_web_lg
uvicorn app.main:app --reload --port 8000
# Docs at http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 — proxies /api/* to :8000
npm run build      # TypeScript check + Vite production build
```

### Smoke Test (Incident Scorer)
```bash
cd backend
python test_scorer.py
```

There is no general test suite beyond `test_scorer.py`. No linting config file exists (no `.flake8`, `pyproject.toml`, or `setup.cfg`).

---

## Environment

Create `backend/.env`. Required keys:

```
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
API_KEY=
APP_ENV=development
```

Optional (enable email/WhatsApp channels):
```
SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / EMAIL_FROM_ADDRESS
IMAP_HOST / IMAP_PORT / ENABLE_EMAIL_POLLER=true / POLL_INTERVAL_SECONDS=30
TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_NUMBER / WEBHOOK_BASE_URL
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

All settings are Pydantic `BaseSettings` in `backend/app/core/config.py`.

---

## Architecture

### Request Flow

```
Channel (web / email / WhatsApp / branch)
    ↓
POST /api/v1/complaints/submit
    ↓ BackgroundTask
POST /api/v1/pipeline/run/{complaint_id}   ← asyncio.create_task()
    ↓
LangGraph pipeline (graph.py)
    ↓
signal_extractor.py  →  complaint_signals table
    ↓
build_clusters()     →  complaint_clusters table
    ↓
GET /api/v1/pipeline/stream/{id}  ← SSE (EventSource)
```

### LangGraph Pipeline — 10-Node DAG

Defined in `backend/app/services/supervisor/graph.py` (~1100 lines).

```
[1] PII & Preprocessing  — spaCy NER + Presidio masking
[2] Duplicate Detection  — OpenAI embeddings + pgvector cosine (threshold 0.92)
                          → if duplicate: END early
[3-6] Parallel fan-out (asyncio.gather):
    [3] Classification   — GPT-4o category + confidence
    [4] Sentiment        — urgency 1–10 + escalation flag
    [5] Compliance       — RBI category + supervisor_override
    [6] Severity         — severity 1–5 with breakdown
[7] RAG Memory           — pgvector KB retrieval (top-3 docs)
[8] Resolution           — GPT-4o draft response (tier-aware prompting)
[9] Grounding            — LLM-as-judge fact-check → SAFE / VERIFY / DO_NOT_SEND
[10] Routing Node        — decides AUTO / HUMAN / ESCALATE
    AUTO   → execute_auto_response() → notify customer via original channel
    HUMAN  → assign_to_queue() → agent_queue table
    ESCALATE → escalation_analyzer() → [Route 3]

[Route 3] Escalation Orchestrator (recursive, max 5 hops)
    Re-runs agents 7–10 at new tier until confidence ≥ 0.75 or max tier reached
```

**PipelineState** (`supervisor/pipeline_state.py`) is a TypedDict with ~105 fields. Accumulating list fields (`explanation_trace`, `errors`, `escalation_path`) use `operator.add` as the LangGraph reducer — always append, never overwrite these.

### Routing Outcomes

| Route | Condition | Result |
|-------|-----------|--------|
| `AUTO` | confidence ≥ 0.75, not fraud/severity-5 | Auto-response sent, complaint closed |
| `HUMAN` | fraud/furious/severity-5 override, or RBI flag | Added to `agent_queue` |
| `ESCALATE` | confidence < 0.75 | Escalation orchestrator runs (Route 3) |

### Tier System

6 tiers (0–5). Mapping is hardcoded in `config.py`:
- Tier 0: General agents (Rishi, Alok, Shaunak)
- Tier 1: Branch (Saket, Prince)
- Tier 2: Zone (Shubham)
- Tier 3: Region (Shubham Kumar)
- Tier 4: Head Office (Sarthak)
- Tier 5: RBI Ombudsman (external)

### Predictive Complaint Intelligence

Runs on a 5-minute APScheduler (starts automatically with uvicorn — no separate process needed):
1. `build_clusters()` — aggregates `complaint_signals` → `complaint_clusters` snapshots grouped by `(event_type, product, region)`
2. `score_pending_clusters()` — scores unscored clusters with LightGBM model

Model artifacts live in `backend/predictiveComplaintIntellegence/` (note the intentional typo in the folder name — do not rename it, the path is hardcoded in `incident_scorer.py` via `Path(__file__).parent.parent.parent`).

API endpoint: `GET /api/v1/clusters/alerts` — returns latest scored snapshot per active cluster, sorted by priority.

### SSE Streaming

Each complaint has an in-memory `asyncio.Queue` in `supervisor/event_bus.py`. The frontend connects to `GET /api/v1/pipeline/stream/{id}` immediately after triggering a pipeline run. The event bus is per-process (not Redis-backed), so multi-worker deployments would break SSE.

### Frontend Structure

- `src/lib/api.ts` — single source of truth for all API calls, typed. All endpoints live under the `api` object.
- `src/hooks/useApiData.ts` — generic fetch hook returning `{ data, loading, error, refetch }`.
- `src/lib/pipelineSse.ts` — SSE listener that dispatches to per-event handlers.
- Main dashboard is a single route (`/complaint`) with tabs: Overview, Complaints, Pipeline, Agent Desk, Analytics (4 sub-tabs), RBI, SLA, KB Admin.

---

## Key Conventions

- **Adding a new API route**: create a file in `backend/app/api/v1/routes/`, register it in `backend/app/api/v1/__init__.py`.
- **Adding a new frontend API method**: add the call in `frontend/src/lib/api.ts` under the appropriate namespace, add the TypeScript type alongside it.
- **Agent nodes**: each node in `graph.py` returns a partial dict of `PipelineState` keys it owns. Never return keys owned by other nodes.
- **Escalation loop guard**: hard cap is 5 hops (`MAX_ESCALATION_ITERATIONS`) with a 10-second per-tier cooldown (`ESCALATION_CACHE_TTL_SECONDS=30`).
- **pgvector**: embeddings are 512-dimensional (Matryoshka truncation of `text-embedding-3-small`). The `complaints` and `knowledge_base` tables both have an `embedding vector(512)` column with IVFFlat indexes.
