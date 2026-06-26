# CIF Customer Summary Feature — Design Spec

**Date:** 2026-06-26  
**Status:** Approved  

---

## Overview

Human agents who receive complaints routed to `human_review` need rapid context on a customer's history before acting. Sending full complaint histories to an LLM on every page load is expensive and slow. This feature introduces a two-tier cached summarization system: a per-complaint digest generated at pipeline milestones, and a CIF-level narrative paragraph assembled from those digests by a background job.

The UI never invokes an LLM. Agents see a ready-made narrative summary in four places across the dashboard.

---

## Goals

- Give human agents a 2–4 sentence customer narrative before they act on a complaint.
- Minimize LLM token usage: the CIF-level LLM call sees only short per-complaint digests, not raw complaint text.
- Keep summaries fresh: CIF summaries regenerate within 1 minute of any complaint milestone.
- Surface the summary in all agent-facing views: complaints table, complaint detail modal, complaint modal, and 360° customer view.

---

## Data Layer

### 1. New column: `complaints.complaint_summary`

Added to the existing `complaints` table in Supabase.

| Column | Type | Notes |
|--------|------|-------|
| `complaint_summary` | `text` | 1–3 sentence digest; NULL until milestone reached |

**Populated when complaint status transitions to any of:**
- `resolved`
- `in_progress`
- `human_review`
- `auto_closed`

**Content:** category, what happened, how it was or is being resolved, customer sentiment signal. Example:
> "ATM cash dispense failure (Severity 3, Frustrated). Customer reported ₹5,000 not dispensed at Andheri branch. Draft response issued for refund initiation; routed to human review due to escalation flag."

### 2. New table: `cif_summaries`

| Column | Type | Notes |
|--------|------|-------|
| `cif_id` | `text` | Primary key |
| `summary_text` | `text` | 2–4 sentence narrative paragraph |
| `complaint_count` | `int` | Number of complaints used to build summary |
| `last_updated` | `timestamptz` | When summary was last regenerated |
| `dirty` | `boolean` | `true` when any complaint for this CIF hit a milestone since last generation |

**`dirty` is set to `true`** (via upsert) immediately after any complaint's `complaint_summary` is written.

---

## Backend Services

### `complaint_summary_service.py`

Location: `backend/app/services/complaint_summary_service.py`

**Responsibility:** Generate and store a 1–3 sentence digest for a single complaint.

**Trigger:** Called from the LangGraph routing node (node 10 in `graph.py`) after the route decision is made and the status reaches a milestone.

**Input fields used:**
- `masked_text` (complaint body — already PII-safe)
- `category`, `sentiment`, `severity`
- `draft_response` (what the AI proposed)
- `route` (AUTO / HUMAN / ESCALATE)
- `current_tier`

**LLM call:** GPT-4o-mini, ~300 tokens, system prompt instructs concise agent-facing digest.

**Output:** Writes `complaint_summary` to the complaint row. Upserts `cif_summaries` row setting `dirty = true`.

**Error handling:** Failures are logged and non-fatal — a missing `complaint_summary` is acceptable; the CIF summary job skips complaints with NULL digests.

---

### `cif_summary_service.py`

Location: `backend/app/services/cif_summary_service.py`

**Responsibility:** Roll up per-complaint digests into a single CIF-level narrative paragraph.

**Trigger:** Called by the APScheduler job every 1 minute.

**Logic:**
1. Query `cif_summaries WHERE dirty = true`.
2. For each dirty `cif_id`, fetch all non-NULL `complaint_summary` values from `complaints` ordered by `created_at`.
3. Call GPT-4o-mini with a structured prompt:
   > "You are helping a bank agent understand a customer's complaint history. Below are summaries of all complaints filed by this customer, oldest first. Write a 2–4 sentence narrative that describes the pattern of issues, how they were resolved, the customer's sentiment trajectory, and any advice for handling the current complaint."
4. Write `summary_text`, `complaint_count`, `last_updated` to `cif_summaries`. Set `dirty = false`.

**Token estimate:** ~50 tokens per complaint digest × up to 20 complaints = ~1000 tokens per CIF regeneration. GPT-4o-mini cost: ~$0.001 per customer.

**Error handling:** On LLM failure, log and leave `dirty = true` so the next tick retries.

---

### Scheduled Job

Location: `backend/app/tasks/scheduled_jobs.py` — new function `refresh_dirty_cif_summaries()`

Wired in `backend/app/main.py` APScheduler setup:
```python
scheduler.add_job(refresh_dirty_cif_summaries, "interval", minutes=1)
```

---

### New API Endpoint

```
GET /api/v1/customers/{cif_id}/summary
```

Response:
```json
{
  "cif_id": "CIF-12345",
  "summary_text": "The customer has experienced...",
  "complaint_count": 4,
  "last_updated": "2026-06-26T10:45:00Z"
}
```

Returns `{ summary_text: null }` (not 404) when no summary exists yet — the frontend renders a graceful empty state.

Route file: `backend/app/api/v1/routes/customers.py` (already exists — add endpoint there).  
Register nothing new in `__init__.py` — customers router is already mounted.

---

## Frontend

### Shared Component: `CustomerSummaryCard`

Location: `frontend/src/components/customers/CustomerSummaryCard.tsx`

**Props:** `cifId: string | null | undefined`

**Behavior:**
- If `cifId` is null/undefined: renders nothing.
- Calls `GET /api/v1/customers/{cifId}/summary` on mount.
- Loading state: skeleton pulse.
- Empty state: "No complaint history on record."
- Populated state: renders the narrative paragraph + metadata line ("Based on 4 complaints · Updated 5 min ago").

Used in all 4 surfaces — no duplication.

---

### Surface 1: Complaints Table — Summary Column

File: `frontend/src/components/complaints/ComplaintsTable.tsx`

- Add `cif_id` to the `ApiComplaint` type in `api.ts` (already present in the `complaints` table — just needs to be included in the `GET /api/v1/complaints/` select query).
- New column "Summary" renders `<CustomerSummaryCard cifId={c.cif_id} />` inline as a compact single-line preview (truncated to 1 line, full card on row expand/hover).

---

### Surface 2: ComplaintDetailModal

File: `frontend/src/components/complaints/ComplaintDetailModal.tsx`

- New "Customer History" collapsible section below the AI analysis panel.
- Renders `<CustomerSummaryCard cifId={apiDetail?.cif_id} />` — only visible when `apiDetail` is loaded (full complaint detail already fetched when modal opens).

---

### Surface 3: 360° Customer View

File: `frontend/src/components/customers/` (existing customer detail view)

- Summary card displayed as the first prominent element at the top of the customer profile, above the stats grid.

---

### Surface 4: ComplaintModal

Same `<CustomerSummaryCard />` as Surface 2 — compact version with a "See full history →" link that navigates to the 360° Customer View.

---

## Data Flow Summary

```
Pipeline node 10 (routing)
    → complaint_summary_service.generate(complaint_id)
        → GPT-4o-mini (300 tokens)
        → complaints.complaint_summary = "1–3 sentence digest"
        → cif_summaries UPSERT dirty = true

APScheduler (every 1 min)
    → refresh_dirty_cif_summaries()
        → SELECT dirty cif_ids
        → for each: fetch complaint_summary rows
        → GPT-4o-mini (~1000 tokens)
        → cif_summaries.summary_text = narrative
        → dirty = false

UI (any of 4 surfaces)
    → GET /api/v1/customers/{cif_id}/summary
        → SELECT from cif_summaries (no LLM)
        → returns { summary_text, complaint_count, last_updated }
```

---

## Files Changed / Created

### New files
| Path | Purpose |
|------|---------|
| `backend/app/services/complaint_summary_service.py` | Per-complaint digest generation |
| `backend/app/services/cif_summary_service.py` | CIF-level narrative rollup |
| `frontend/src/components/customers/CustomerSummaryCard.tsx` | Shared summary UI component |

### Modified files
| Path | Change |
|------|--------|
| `backend/app/services/supervisor/graph.py` | Call `complaint_summary_service` at node 10 after routing |
| `backend/app/tasks/scheduled_jobs.py` | Add `refresh_dirty_cif_summaries()` |
| `backend/app/main.py` | Wire scheduler job (1-minute interval) |
| `backend/app/api/v1/routes/customers.py` | Add `GET /{cif_id}/summary` endpoint |
| `backend/app/api/v1/routes/complaints.py` | Include `cif_id` in list query select |
| `frontend/src/lib/api.ts` | Add `customers.getSummary(cifId)` method; add `cif_id` to `ApiComplaint` |
| `frontend/src/types/index.ts` | Add `CustomerSummary` type |
| `frontend/src/components/complaints/ComplaintsTable.tsx` | Add Summary column |
| `frontend/src/components/complaints/ComplaintDetailModal.tsx` | Add Customer History section |
| `frontend/src/components/customers/` | Add summary card to customer detail view |

### Database migration
- `ALTER TABLE complaints ADD COLUMN complaint_summary text;`
- `CREATE TABLE cif_summaries (cif_id text PRIMARY KEY, summary_text text, complaint_count int, last_updated timestamptz, dirty boolean DEFAULT false);`

---

## Out of Scope

- Real-time streaming of summary generation to the UI (summaries are always pre-generated)
- Manual "regenerate" button (can be added later; out of scope for now)
- Multi-language summary support
