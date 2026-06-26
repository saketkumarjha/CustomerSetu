# CIF Customer Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-tier cached summarization system that generates per-complaint digests at pipeline milestones, rolls them into a CIF-level narrative via a background job, and surfaces the result in four frontend locations with zero LLM calls at read time.

**Architecture:** Each complaint gets a 1–3 sentence `complaint_summary` written to the `complaints` table when it reaches a milestone status. A 1-minute APScheduler job reads all dirty CIF IDs, stitches their complaint summaries with GPT-4o-mini into a narrative paragraph, and stores it in a new `cif_summaries` table. The UI fetches the cached result from `GET /api/v1/customers/{cif_id}/summary` — a plain DB read.

**Tech Stack:** Python 3.11, FastAPI, Supabase (PostgreSQL via PostgREST), OpenAI GPT-4o-mini, APScheduler, React 18, TypeScript, Tailwind CSS.

## Global Constraints

- All LLM calls use `gpt-4o-mini` model via `openai` Python SDK (same as rest of codebase).
- Backend env vars are in `backend/.env` and accessed via `app.core.config.get_settings()`.
- All new backend files go under `backend/app/`.
- All new frontend files go under `frontend/src/`.
- Frontend API calls use `apiGet` from `frontend/src/lib/api.ts` with auth headers — never bare `fetch`.
- `cif_id` already exists on `ApiComplaint` as `cif_id?: string | null`.
- Never remove PII: use `masked_text` not `original_text` in any LLM prompt.
- Supabase client is obtained via `get_supabase()` from `app.db.supabase_client`.

---

## File Map

### New files
| Path | Responsibility |
|------|---------------|
| `backend/app/services/complaint_summary_service.py` | Generate 1–3 sentence per-complaint digest; mark CIF dirty |
| `backend/app/services/cif_summary_service.py` | Roll up complaint digests into CIF narrative; clear dirty flag |
| `frontend/src/components/customers/CustomerSummaryCard.tsx` | Shared UI component used in all 4 surfaces |

### Modified files
| Path | Change |
|------|--------|
| `backend/app/services/supervisor/graph.py` | Call `generate_complaint_summary` at end of `routing_node` |
| `backend/app/tasks/scheduled_jobs.py` | Add `refresh_dirty_cif_summaries()` async function |
| `backend/app/main.py` | Wire 1-minute scheduler job |
| `backend/app/api/v1/routes/customers.py` | Add `GET /{cif_id}/summary` endpoint |
| `backend/app/api/v1/routes/complaints.py` | Add `complaint_summary` to single-complaint select |
| `frontend/src/lib/api.ts` | Add `CustomerSummary` interface + `customers.getSummary()` method |
| `frontend/src/types/index.ts` | Add `CustomerSummary` re-export (optional, for convenience) |
| `frontend/src/components/complaints/ComplaintsTable.tsx` | Add Summary column |
| `frontend/src/components/complaints/ComplaintDetailModal.tsx` | Add Customer History section |
| `frontend/src/components/customers/CustomerDetailView.tsx` (or equivalent customer detail file) | Add summary card at top |

---

## Task 1: Database Migration

**Files:**
- No code files — Supabase SQL migration run manually or via Supabase dashboard

**Interfaces:**
- Produces: `complaints.complaint_summary text` column; `cif_summaries` table

- [ ] **Step 1: Run migration SQL in Supabase SQL editor**

```sql
-- Add complaint_summary column to complaints table
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS complaint_summary text;

-- Create cif_summaries cache table
CREATE TABLE IF NOT EXISTS cif_summaries (
  cif_id        text PRIMARY KEY,
  summary_text  text,
  complaint_count int,
  last_updated  timestamptz,
  dirty         boolean NOT NULL DEFAULT false
);
```

- [ ] **Step 2: Verify columns exist**

In Supabase Table Editor, confirm:
- `complaints` table has a `complaint_summary` column of type `text` (nullable).
- `cif_summaries` table exists with columns: `cif_id`, `summary_text`, `complaint_count`, `last_updated`, `dirty`.

- [ ] **Step 3: Commit a migration note**

```bash
git add -A
git commit -m "chore: add complaint_summary column and cif_summaries table (migration applied)"
```

---

## Task 2: `complaint_summary_service.py`

**Files:**
- Create: `backend/app/services/complaint_summary_service.py`

**Interfaces:**
- Consumes: `complaint_id: str`, Supabase `complaints` row fields (`masked_text`, `category`, `sentiment`, `severity`, `draft_response`, `route`, `current_tier`, `cif_id`)
- Produces: `generate_complaint_summary(complaint_id: str) -> None` — writes `complaint_summary` to DB and upserts `cif_summaries` dirty flag

- [ ] **Step 1: Create the service file**

```python
"""
Complaint Summary Service — generate a 1–3 sentence digest for a single complaint.

Called from routing_node (graph.py) after route decision.
Writes complaint_summary to complaints table and marks cif_summaries dirty.
"""
import logging
from openai import OpenAI
from app.db.supabase_client import get_supabase
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a concise assistant summarising a bank complaint for a human agent. "
    "Write exactly 1–3 sentences covering: (1) complaint category and what went wrong, "
    "(2) how it was or is being handled, (3) customer sentiment. "
    "Be factual, professional, and under 60 words. Do not include customer names or account numbers."
)


def generate_complaint_summary(complaint_id: str) -> None:
    """
    Generate a 1–3 sentence digest for complaint_id and persist it.
    Also marks the customer's cif_summaries row as dirty.
    Non-fatal: logs and returns on any error.
    """
    try:
        supabase = get_supabase()
        settings = get_settings()

        # Fetch complaint fields needed for the prompt
        result = (
            supabase.table("complaints")
            .select("masked_text, category, sentiment, severity, draft_response, route, current_tier, cif_id")
            .eq("complaint_id", complaint_id)
            .single()
            .execute()
        )
        if not result.data:
            logger.warning("[SUMMARY] complaint %s not found — skipping", complaint_id)
            return

        c = result.data
        cif_id = c.get("cif_id")

        # Build the user message
        route_label = {
            "AUTO": "auto-resolved",
            "HUMAN": "routed to human review",
            "ESCALATE": "escalated",
        }.get((c.get("route") or "").upper(), c.get("route") or "pending")

        user_msg = (
            f"Category: {c.get('category') or 'Unknown'}\n"
            f"Sentiment: {c.get('sentiment') or 'Unknown'}\n"
            f"Severity: {c.get('severity') or 'Unknown'}/5\n"
            f"Complaint text: {(c.get('masked_text') or '')[:800]}\n"
            f"AI draft response: {(c.get('draft_response') or 'None')[:400]}\n"
            f"Routing decision: {route_label}\n"
            f"Handling tier: {c.get('current_tier') or 1}"
        )

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=120,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()

        # Write complaint_summary back to complaints table
        supabase.table("complaints").update(
            {"complaint_summary": summary}
        ).eq("complaint_id", complaint_id).execute()
        logger.info("[SUMMARY] wrote complaint_summary for %s", complaint_id)

        # Mark CIF as dirty so the background job regenerates the CIF narrative
        if cif_id:
            supabase.table("cif_summaries").upsert(
                {"cif_id": cif_id, "dirty": True},
                on_conflict="cif_id",
            ).execute()
            logger.info("[SUMMARY] marked cif_summaries dirty for cif=%s", cif_id)

    except Exception as exc:
        logger.error("[SUMMARY] generate_complaint_summary(%s) failed: %s", complaint_id, exc)
```

- [ ] **Step 2: Manually verify OpenAI import path**

The rest of the codebase uses `from openai import OpenAI`. Confirm the same pattern is used in `backend/app/services/agents/resolution_agent.py`:

```bash
grep -n "from openai" backend/app/services/agents/resolution_agent.py
```

Expected output should include `from openai import OpenAI` or similar. If the pattern differs, match it.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/complaint_summary_service.py
git commit -m "feat: add complaint_summary_service — per-complaint digest via gpt-4o-mini"
```

---

## Task 3: `cif_summary_service.py`

**Files:**
- Create: `backend/app/services/cif_summary_service.py`

**Interfaces:**
- Consumes: `cif_summaries` table (dirty rows), `complaints.complaint_summary`
- Produces: `refresh_dirty_cif_summaries() -> dict` — updates `cif_summaries.summary_text`, returns `{"processed": int, "errors": int}`

- [ ] **Step 1: Create the service file**

```python
"""
CIF Summary Service — roll up per-complaint digests into a customer narrative.

Called by APScheduler every 1 minute.
Reads dirty cif_ids, stitches complaint_summary rows, calls gpt-4o-mini,
writes the narrative back to cif_summaries.
"""
import logging
from datetime import datetime, timezone
from openai import OpenAI
from app.db.supabase_client import get_supabase
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior bank complaints analyst. "
    "Below are short summaries of all complaints filed by one customer, oldest first. "
    "Write a 2–4 sentence narrative for a human agent that covers: "
    "(1) the pattern of issues the customer has experienced, "
    "(2) how previous complaints were resolved, "
    "(3) the customer's sentiment trajectory, "
    "(4) practical advice for handling the current complaint. "
    "Be professional, specific, and under 100 words. Do not invent facts."
)


async def refresh_dirty_cif_summaries() -> dict:
    """
    Find all CIFs marked dirty, regenerate their narrative summaries, clear dirty flag.
    Returns {"processed": N, "errors": N}.
    """
    supabase = get_supabase()
    settings = get_settings()

    # Find all dirty CIFs
    dirty_resp = (
        supabase.table("cif_summaries")
        .select("cif_id")
        .eq("dirty", True)
        .execute()
    )
    dirty_rows = dirty_resp.data or []

    if not dirty_rows:
        return {"processed": 0, "errors": 0}

    client = OpenAI(api_key=settings.openai_api_key)
    processed = 0
    errors = 0

    for row in dirty_rows:
        cif_id = row["cif_id"]
        try:
            # Fetch all non-null complaint summaries for this CIF, oldest first
            comp_resp = (
                supabase.table("complaints")
                .select("complaint_summary, created_at, category")
                .eq("cif_id", cif_id)
                .not_.is_("complaint_summary", "null")
                .order("created_at", desc=False)
                .execute()
            )
            summaries = comp_resp.data or []

            if not summaries:
                # Nothing to summarise yet — clear dirty and skip
                supabase.table("cif_summaries").update({"dirty": False}).eq("cif_id", cif_id).execute()
                continue

            # Build numbered list for the LLM
            lines = [
                f"{i+1}. [{s.get('category') or 'Unknown'}] {s['complaint_summary']}"
                for i, s in enumerate(summaries)
            ]
            user_msg = "\n".join(lines)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=160,
                temperature=0.3,
            )
            narrative = response.choices[0].message.content.strip()

            supabase.table("cif_summaries").upsert(
                {
                    "cif_id": cif_id,
                    "summary_text": narrative,
                    "complaint_count": len(summaries),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "dirty": False,
                },
                on_conflict="cif_id",
            ).execute()

            logger.info("[CIF_SUMMARY] regenerated narrative for cif=%s (%d complaints)", cif_id, len(summaries))
            processed += 1

        except Exception as exc:
            logger.error("[CIF_SUMMARY] failed for cif=%s: %s", cif_id, exc)
            errors += 1
            # Leave dirty=True so the next tick retries

    return {"processed": processed, "errors": errors}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/cif_summary_service.py
git commit -m "feat: add cif_summary_service — CIF narrative rollup via gpt-4o-mini"
```

---

## Task 4: Wire into Pipeline (graph.py) and Scheduler (main.py)

**Files:**
- Modify: `backend/app/services/supervisor/graph.py` — end of `routing_node` function
- Modify: `backend/app/tasks/scheduled_jobs.py` — add `refresh_dirty_cif_summaries`
- Modify: `backend/app/main.py` — add 1-minute scheduler job

**Interfaces:**
- Consumes: `generate_complaint_summary` from Task 2; `refresh_dirty_cif_summaries` from Task 3
- Produces: pipeline trigger + scheduled job running every 1 minute

- [ ] **Step 1: Add call to `routing_node` in `graph.py`**

At the very end of `routing_node`, just before the `return { ... }` dict (around line 1012), add:

```python
    # Generate per-complaint summary digest (non-blocking, non-fatal)
    try:
        from app.services.complaint_summary_service import generate_complaint_summary
        generate_complaint_summary(complaint_id)
    except Exception as _summary_err:
        logger.warning("[ROUTING] complaint summary generation failed: %s", _summary_err)
```

Make sure this is added BEFORE the `return` statement at line ~1013.

- [ ] **Step 2: Add `refresh_dirty_cif_summaries` to `scheduled_jobs.py`**

Open `backend/app/tasks/scheduled_jobs.py` and add at the bottom of the file:

```python
async def refresh_dirty_cif_summaries() -> dict:
    """
    Wrapper called by APScheduler every 1 minute.
    Delegates to cif_summary_service.
    """
    from app.services.cif_summary_service import refresh_dirty_cif_summaries as _refresh
    return await _refresh()
```

- [ ] **Step 3: Wire scheduler in `main.py`**

In `backend/app/main.py`, inside the `lifespan` function, after the existing `_scheduler.add_job(score_pending_clusters, ...)` block and before `_scheduler.start()`:

```python
    from app.tasks.scheduled_jobs import refresh_dirty_cif_summaries
    _scheduler.add_job(
        refresh_dirty_cif_summaries,
        "interval",
        minutes=1,
        id="refresh_cif_summaries",
        max_instances=1,
        coalesce=True,
    )
```

- [ ] **Step 4: Start backend and verify scheduler logs**

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

Expected log line within 60 seconds:
```
[CIF_SUMMARY] ... (processed: 0, errors: 0)   ← no dirty rows yet, that's fine
```

If you see an import error, check that `complaint_summary_service.py` and `cif_summary_service.py` are in `backend/app/services/`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/supervisor/graph.py backend/app/tasks/scheduled_jobs.py backend/app/main.py
git commit -m "feat: wire complaint summary generation into routing_node and 1-min scheduler"
```

---

## Task 5: API Endpoint `GET /api/v1/customers/{cif_id}/summary`

**Files:**
- Modify: `backend/app/api/v1/routes/customers.py`

**Interfaces:**
- Consumes: `cif_summaries` table
- Produces: `GET /{cif_id}/summary` → `{ cif_id, summary_text, complaint_count, last_updated }`; returns `{ cif_id, summary_text: null, complaint_count: 0, last_updated: null }` when not found (no 404)

- [ ] **Step 1: Add the endpoint to `customers.py`**

Add this after the existing `get_customer` function (after line ~240 of the current file):

```python
@router.get("/{cif_id}/summary", summary="Get cached CIF narrative summary")
def get_cif_summary(cif_id: str):
    """
    Return the cached CIF-level narrative summary.
    Returns summary_text: null when no summary exists yet — frontend handles this gracefully.
    Never returns 404; always returns a valid JSON object.
    """
    supabase = get_supabase()
    result = (
        supabase.table("cif_summaries")
        .select("cif_id, summary_text, complaint_count, last_updated")
        .eq("cif_id", cif_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return {
        "cif_id": cif_id,
        "summary_text": None,
        "complaint_count": 0,
        "last_updated": None,
    }
```

**Important:** This route must be placed AFTER `GET /{cif_id}` in the file so FastAPI doesn't match `/summary` as a `cif_id` value. Check that `GET /{cif_id}` is defined before this new route.

- [ ] **Step 2: Test the endpoint manually**

With the backend running:
```bash
curl -H "X-API-Key: sk_my_super_secret_key_123" \
  http://localhost:8000/api/v1/customers/SOME_CIF_ID/summary
```

Expected response (before any summaries exist):
```json
{"cif_id": "SOME_CIF_ID", "summary_text": null, "complaint_count": 0, "last_updated": null}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/routes/customers.py
git commit -m "feat: add GET /api/v1/customers/{cif_id}/summary endpoint"
```

---

## Task 6: Frontend Types and API Client

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- Produces:
  - `CustomerSummary` interface: `{ cif_id: string; summary_text: string | null; complaint_count: number; last_updated: string | null }`
  - `api.customers.getSummary(cifId: string): Promise<CustomerSummary>`

- [ ] **Step 1: Add `CustomerSummary` interface to `types/index.ts`**

In `frontend/src/types/index.ts`, after the `CustomerDetail` interface (around line 68), add:

```typescript
export interface CustomerSummary {
  cif_id: string;
  summary_text: string | null;
  complaint_count: number;
  last_updated: string | null;
}
```

- [ ] **Step 2: Add `getSummary` to the customers namespace in `api.ts`**

Find the `customers` object in `frontend/src/lib/api.ts`. Add the `getSummary` method alongside existing customer methods:

```typescript
getSummary: (cifId: string): Promise<CustomerSummary> =>
  apiGet<CustomerSummary>(`/api/v1/customers/${encodeURIComponent(cifId)}/summary`),
```

Also add the import at the top of the api.ts customers section or inline — `CustomerSummary` must be imported from `../types` or defined locally. Since it's in `types/index.ts`, add the import:

```typescript
import type { CustomerSummary } from "../types";
```

(Place this near other type imports at the top of `api.ts`, or use an inline interface if you prefer to keep `api.ts` self-contained.)

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors related to `CustomerSummary` or `getSummary`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/types/index.ts
git commit -m "feat: add CustomerSummary type and api.customers.getSummary method"
```

---

## Task 7: `CustomerSummaryCard` Shared Component

**Files:**
- Create: `frontend/src/components/customers/CustomerSummaryCard.tsx`

**Interfaces:**
- Consumes: `api.customers.getSummary` from Task 6; `CustomerSummary` type from Task 6
- Produces: `<CustomerSummaryCard cifId={string | null | undefined} compact={boolean} />` — `compact=true` renders single-line truncated; `compact=false` (default) renders full card with metadata

- [ ] **Step 1: Create the component**

```tsx
import { useEffect, useState } from "react";
import { BookOpen, Clock } from "lucide-react";
import { api } from "../../lib/api";
import type { CustomerSummary } from "../../types";

interface Props {
  cifId: string | null | undefined;
  compact?: boolean;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff}m ago`;
  const h = Math.floor(diff / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function CustomerSummaryCard({ cifId, compact = false }: Props) {
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!cifId) return;
    setLoading(true);
    api.customers
      .getSummary(cifId)
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [cifId]);

  if (!cifId) return null;

  if (loading) {
    return (
      <div className="animate-pulse rounded-lg bg-slate-100 h-12 w-full" />
    );
  }

  if (!summary?.summary_text) {
    return (
      <p className="text-xs text-slate-400 italic">No complaint history on record.</p>
    );
  }

  if (compact) {
    return (
      <p className="text-xs text-slate-600 line-clamp-1 leading-relaxed">
        {summary.summary_text}
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50/60 p-3 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-ub-blue">
        <BookOpen size={12} />
        Customer History Summary
      </div>
      <p className="text-xs text-slate-700 leading-relaxed">{summary.summary_text}</p>
      <div className="flex items-center gap-1 text-[10px] text-slate-400">
        <Clock size={10} />
        Based on {summary.complaint_count} complaint
        {summary.complaint_count !== 1 ? "s" : ""} · Updated{" "}
        {timeAgo(summary.last_updated)}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/customers/CustomerSummaryCard.tsx
git commit -m "feat: add CustomerSummaryCard shared component"
```

---

## Task 8: Surface 1 — Complaints Table Column

**Files:**
- Modify: `frontend/src/components/complaints/ComplaintsTable.tsx`

**Interfaces:**
- Consumes: `<CustomerSummaryCard cifId compact />` from Task 7; `ApiComplaint.cif_id` (already present)
- Produces: new "History" column in the complaints table showing compact summary per row

- [ ] **Step 1: Import `CustomerSummaryCard` at the top of `ComplaintsTable.tsx`**

Add after existing imports:

```tsx
import { CustomerSummaryCard } from "../customers/CustomerSummaryCard";
```

- [ ] **Step 2: Add `cif_id` prop mapping**

In `ComplaintsTable.tsx`, the complaints come from the parent via the `complaints` prop (type `Complaint[]`). However `cif_id` is on `ApiComplaint`, not on the mapped `Complaint` type. The cleanest approach is to accept an optional `cifIdMap` prop:

Add to the `Props` interface of `ComplaintsTable`:
```tsx
cifIdMap?: Map<string, string>; // complaint_id → cif_id
```

In `ComplaintsTab.tsx`, build this map when `apiData` is available:
```tsx
const cifIdMap = new Map<string, string>();
for (const c of apiData?.complaints ?? []) {
  if (c.cif_id) cifIdMap.set(c.complaint_id, c.cif_id);
}
```

Pass it to `<ComplaintsTable ... cifIdMap={cifIdMap} />`.

- [ ] **Step 3: Add the "History" column to the table**

In `ComplaintsTable.tsx`, find the table header row and add a new `<th>`:

```tsx
<th className="px-3 py-2 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wide w-48">
  History
</th>
```

In the table body row, add the corresponding `<td>`:

```tsx
<td className="px-3 py-2 max-w-[192px]">
  <CustomerSummaryCard
    cifId={cifIdMap?.get(c.id)}
    compact
  />
</td>
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/complaints/ComplaintsTable.tsx frontend/src/components/complaints/ComplaintsTab.tsx
git commit -m "feat: add History column to complaints table using CustomerSummaryCard"
```

---

## Task 9: Surface 2 & 4 — ComplaintDetailModal

**Files:**
- Modify: `frontend/src/components/complaints/ComplaintDetailModal.tsx`

**Interfaces:**
- Consumes: `<CustomerSummaryCard cifId={apiDetail?.cif_id} />` from Task 7; `apiDetail: ApiComplaint | null` (already a prop)
- Produces: "Customer History" collapsible section in the modal

- [ ] **Step 1: Import `CustomerSummaryCard`**

Add to existing imports in `ComplaintDetailModal.tsx`:
```tsx
import { CustomerSummaryCard } from "../customers/CustomerSummaryCard";
```

- [ ] **Step 2: Add collapsible "Customer History" section**

Find where the AI analysis section ends in the modal (look for a closing `</div>` after the last analysis panel). Add a new collapsible section immediately after the DuplicateBanner:

```tsx
{/* Customer History Summary */}
{apiDetail?.cif_id && (
  <div className="border border-slate-200 rounded-lg overflow-hidden">
    <button
      className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 hover:bg-slate-100 text-sm font-semibold text-slate-700 transition-colors"
      onClick={() => setShowHistory(h => !h)}
    >
      <span className="flex items-center gap-2">
        <BookOpen size={14} className="text-ub-blue" />
        Customer History
      </span>
      {showHistory ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
    </button>
    {showHistory && (
      <div className="p-4 space-y-3">
        <CustomerSummaryCard cifId={apiDetail.cif_id} />
        <a
          href="#"
          onClick={e => { e.preventDefault(); onClose(); /* navigate to customers tab */ }}
          className="text-xs text-ub-blue hover:underline"
        >
          See full history →
        </a>
      </div>
    )}
  </div>
)}
```

Add `const [showHistory, setShowHistory] = useState(false);` to the component's state declarations.

Add `BookOpen` to the lucide-react import line.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/complaints/ComplaintDetailModal.tsx
git commit -m "feat: add Customer History collapsible section to ComplaintDetailModal"
```

---

## Task 10: Surface 3 — 360° Customer View

**Files:**
- Modify: the customer detail view component in `frontend/src/components/customers/`

**Interfaces:**
- Consumes: `<CustomerSummaryCard cifId={cif_id} />` from Task 7; the `cif_id` is already available on the customer detail page

- [ ] **Step 1: Locate the customer detail component**

```bash
ls frontend/src/components/customers/
```

Find the component that renders the full customer profile (likely `CustomerDetailView.tsx` or the detail section within a parent component).

- [ ] **Step 2: Import and place `CustomerSummaryCard`**

Add import:
```tsx
import { CustomerSummaryCard } from "./CustomerSummaryCard";
```

Place the card at the very top of the customer detail body, before the stats grid. Use the `cif_id` from the customer detail data:

```tsx
{/* Customer narrative summary — shown prominently before stats */}
<div className="mb-4">
  <CustomerSummaryCard cifId={customer.cif_id} />
</div>
```

Where `customer.cif_id` is the CIF ID from the loaded customer detail.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/customers/
git commit -m "feat: add CustomerSummaryCard to 360° customer detail view"
```

---

## Task 11: End-to-End Smoke Test

**No new files — validation only.**

- [ ] **Step 1: Submit a test complaint via the web form**

Start both servers:
```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000
# Terminal 2
cd frontend && npm run dev
```

Submit a complaint for a customer with a known `cif_id` (or any complaint — the pipeline will assign one if identity resolution runs).

- [ ] **Step 2: Verify complaint_summary is written**

After the pipeline completes (watch the SSE stream on the Pipeline tab), check in Supabase Table Editor:
- `complaints` table → find the new complaint → `complaint_summary` should be a non-null 1–3 sentence string.

- [ ] **Step 3: Verify cif_summaries is marked dirty**

In Supabase Table Editor → `cif_summaries` → find the row with the matching `cif_id` → `dirty` should be `true`.

- [ ] **Step 4: Wait 1 minute, verify narrative is generated**

After 60 seconds, reload the `cif_summaries` row:
- `summary_text` should contain a 2–4 sentence narrative.
- `dirty` should be `false`.
- `complaint_count` should equal the number of complaints with non-null `complaint_summary` for this CIF.

- [ ] **Step 5: Verify the API endpoint**

```bash
curl -H "X-API-Key: sk_my_super_secret_key_123" \
  "http://localhost:8000/api/v1/customers/YOUR_CIF_ID/summary"
```

Expected:
```json
{
  "cif_id": "YOUR_CIF_ID",
  "summary_text": "The customer has experienced...",
  "complaint_count": 1,
  "last_updated": "2026-06-26T..."
}
```

- [ ] **Step 6: Verify all 4 UI surfaces**

Open the frontend at `http://localhost:5173`:

1. **Complaints Table** — the "History" column should show a compact 1-line summary for complaints from customers with a CIF.
2. **ComplaintDetailModal** — click a complaint → "Customer History" section should appear and expand to show the full card.
3. **360° Customer View** — navigate to the Customers tab → click a customer → the summary card should appear at the top.
4. **ComplaintModal** — same as #2.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end smoke test passed — CIF customer summary feature complete"
```

---

## Self-Review

**Spec coverage:**
- ✅ `complaint_summary` column populated at 4 milestones (resolved, in_progress, human_review, auto_closed) — `routing_node` fires after route decision; route maps to these statuses
- ✅ `cif_summaries` table with dirty flag
- ✅ 1-minute APScheduler job
- ✅ `GET /api/v1/customers/{cif_id}/summary` — null-safe, no 404
- ✅ `CustomerSummaryCard` shared component — loading / empty / populated states
- ✅ All 4 UI surfaces: complaints table, detail modal, 360° view, complaint modal
- ✅ GPT-4o-mini for both LLM calls
- ✅ Non-fatal error handling on both services

**Type consistency check:**
- `CustomerSummary.summary_text` is `string | null` in both `types/index.ts` (Task 6) and used as `summary?.summary_text` in `CustomerSummaryCard` (Task 7) — consistent.
- `api.customers.getSummary(cifId)` returns `Promise<CustomerSummary>` — consistent with the backend response shape.
- `cifIdMap: Map<string, string>` — `complaint_id → cif_id` — consistent between Task 8 step 2 (build) and step 3 (consume).

**Placeholder check:** No TBDs, TODOs, or "implement later" found.
