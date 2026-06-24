# Session Handoff — Complaint Dashboard (Anijeet)

**Date:** 2026-06-23  
**Branch:** main

---

## Project Overview

A full-stack bank complaint management system with:
- **Backend:** FastAPI + LangGraph multi-agent pipeline (Python), hosted on Azure App Service
- **Frontend:** React + TypeScript + Tailwind, Vite dev server
- **Database:** Supabase (PostgreSQL)
- **AI:** OpenAI GPT-4o for per-complaint agents; LightGBM for predictive ML

The pipeline handles per-complaint tasks (classification, sentiment, severity, deduplication, compliance, routing, auto-response). A separate **Predictive Complaint Intelligence** layer watches complaint patterns across all customers.

---

## Feature Added This Session: Predictive Complaint Intelligence

### What it does
Aggregates individual complaint signals into rolling time-window cluster snapshots, scores them with a trained LightGBM model, and surfaces emerging incidents to agents before they become widespread.

- One complaint = a data point. A **pattern** of complaints = a signal.
- Clusters are grouped by `(event_type, product, region)`.
- Evidence gate: minimum 2 distinct customers in 24h before scoring fires.
- Output: calibrated `risk_score` (0–100), `alert_priority` (low/medium/high/critical), department routing, SHAP explanations.

### Architecture
```
complaint_signals  ←  signal_extractor.py (runs after each pipeline)
        ↓
complaint_clusters ←  cluster_builder.py (build_clusters, every 5 min via APScheduler)
        ↓
   ML scoring     ←  incident_scorer.py (score_pending_clusters, every 5 min)
        ↓
  /clusters/alerts ←  clusters.py API route (polled by frontend every 60s)
        ↓
 AgentDeskTab.tsx  ←  "Active Incident Alerts" panel (broadcast to all agents)
```

### Scheduler
The APScheduler starts **automatically with the backend** inside FastAPI's `lifespan` context (`main.py:82–103`). No separate worker process needed. Runs `build_clusters()` then `score_pending_clusters()` every 5 minutes.

---

## Files Modified / Created This Session

### Bug Fixes

| File | Change | Reason |
|------|--------|--------|
| `backend/app/services/cluster_builder.py` | Removed orphaned `except Exception:` block (lines 253–254) | **Critical SyntaxError** — prevented the entire module from loading; scheduler never started |
| `backend/app/services/incident_scorer.py` | Changed `sv[0]` → `sv[1]` in SHAP value extraction (line 130) | **Wrong SHAP class** — for sklearn-wrapped LGBMClassifier, `sv[0]` is the negative class; positive class is `sv[1]`, so `raises`/`lowers` directions were flipped |

### New Files

| File | Purpose |
|------|---------|
| `backend/app/api/v1/routes/clusters.py` | `GET /api/v1/clusters/alerts` — returns latest scored snapshot per active cluster, deduped, sorted critical-first, with department routing attached |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/api/v1/__init__.py` | Imported `clusters` router; registered at prefix `/clusters` with `Incidents` tag |
| `frontend/src/lib/api.ts` | Added `IncidentAlert` and `IncidentAlertsResponse` types; added `api.incidents.list()` method hitting `GET /api/v1/clusters/alerts` |
| `frontend/src/components/agent/AgentDeskTab.tsx` | Added `IncidentAlertCard` component, `PRIORITY_CONFIG` lookup, `formatEventType()` / `formatAgo()` helpers; wired `useApiData` + 60s `setInterval` polling; added "Active Incident Alerts" panel in JSX between the identity section and "Your numbers" |

---

## Key Design Decisions

**Polling over SSE for alerts**
The existing `event_bus` is complaint-scoped (per `complaint_id` queue). Adding a system-level broadcast SSE channel would require a separate pub/sub mechanism (or Redis for multi-worker). Since alerts change at most every 5 minutes (scheduler cadence), 60-second polling via `useApiData` + `setInterval` is sufficient and much simpler.

**Broadcast, not assigned**
Alerts are shown to all agents regardless of tier or staff ID. The `departments` list on each card tells each agent whether the alert is relevant to their role. No backend assignment logic needed.

**View-only alerts (no acknowledge)**
No `alert_events` table or acknowledgment endpoint was added. The alerts panel is read-only. If acknowledgment is added later, it will need: a new DB column (`acknowledged_by`, `acknowledged_at`) on `complaint_clusters`, and a `POST /clusters/{id}/acknowledge` endpoint.

**Deduplication in Python, not SQL**
Supabase's Python client doesn't support `DISTINCT ON`. The backend fetches the last 500 rows ordered by `snapshot_time DESC`, then deduplicates by `cluster_id` in Python (keeping first = latest per cluster). This is safe given the low cardinality of cluster IDs in practice.

**Department routing from memory**
`clusters.py` imports `ROUTING_TABLE` and `DEFAULT_DEPARTMENTS` directly from `incident_scorer.py` at request time (lazy import inside the handler). If the model fails to load, `departments` returns `[]` rather than crashing.

---

## Model Artifacts

Located at `backend/predictiveComplaintIntellegence/` (note the typo in the folder name — keep it as-is to avoid breaking the path resolution in `incident_scorer.py`):

| File | Content |
|------|---------|
| `incident_model.pkl` | Trained LightGBM model (Booster or LGBMClassifier) |
| `calibrator.pkl` | `sklearn.isotonic.IsotonicRegression` — calibrates raw probabilities |
| `feature_cols.json` | 15 feature names the model expects |
| `routing_table.json` | `event_type → [departments]` mapping + default fallback |

The path is resolved 3 levels up from `incident_scorer.py` using `Path(__file__).parent.parent.parent`.

---

## What's Not Yet Built (future work)

- **Acknowledge / dismiss alerts** — needs DB column + API endpoint
- **Alert history / timeline** — currently only latest snapshot per cluster is surfaced
- **SHAP top-drivers in the frontend** — `incident_scorer.py` computes them but the clusters API endpoint doesn't return them yet (can be added to the SELECT query)
- **Real-time push** — would need a cluster-scoped SSE channel or WebSocket
- **`alert_events` table** — for audit trail of when alerts fired and who acted
