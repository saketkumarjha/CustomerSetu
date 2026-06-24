# Cross-Channel Duplicate Complaint Merge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect semantically similar complaints (≥ 0.85 cosine similarity) across channels, flag them for agent review, and allow agents to merge the secondary into the primary with full UI support.

**Architecture:** Detection runs post-pipeline in a dedicated `duplicate_service.py` — it queries pgvector for similar complaints across all channels, flags both records, and stores cross-references in a `duplicate_of uuid[]` column. Two new API endpoints handle merge and same-person confirmation. Frontend surfaces amber badges in the complaint table and a contextual banner in the detail view with a side-by-side merge modal.

**Tech Stack:** FastAPI, Supabase (pgvector cosine similarity), React + TypeScript, existing `supabase-js` client pattern.

## Global Constraints

- LangGraph pipeline (`graph.py`) must NOT be modified
- `duplicate_of uuid[]` is the cross-channel dedup column — the old single-UUID `duplicate_of` was deleted from the DB; this replaces it
- `pipeline.py` `_save_pipeline_outputs()` no longer writes `duplicate_of`; that column is owned entirely by `duplicate_service.py`
- All backend routes follow the pattern in existing route files: `APIRouter()`, `get_supabase()` for DB access
- Frontend API calls go through `frontend/src/lib/api.ts` — no direct fetch calls in components
- cosine similarity threshold: **0.85** (not 0.92 — that's Node 2's threshold)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| **SQL** | Run in Supabase dashboard | Add 3 columns to `complaints` |
| **Create** | `backend/app/services/duplicate_service.py` | `detect_cross_channel_duplicates()` |
| **Create** | `backend/app/api/v1/routes/duplicates.py` | POST /merge, POST /{id}/confirm-same-person |
| **Modify** | `backend/app/api/v1/__init__.py` | Register duplicates router |
| **Modify** | `backend/app/api/v1/routes/pipeline.py` | Call detect after pipeline completes |
| **Modify** | `frontend/src/lib/api.ts` | Types + merge/confirm API methods |
| **Modify** | `frontend/src/components/ComplaintsTab.tsx` | Amber badge + Resolve button in table |
| **Modify** | `frontend/src/components/agent/AgentDeskTab.tsx` | Duplicate banner + merge modal |

---

## Task 1: Database Migration

**Files:**
- SQL to run manually in Supabase dashboard

**Interfaces:**
- Produces: `complaints.duplicate_status`, `complaints.duplicate_of`, `complaints.merged_into` columns

- [ ] **Step 1: Run SQL in Supabase dashboard**

```sql
alter table complaints
  add column duplicate_status    text check (
    duplicate_status in ('possible_duplicate', 'confirmed_duplicate', 'merged')
  ),
  add column duplicate_of uuid[]  not null default '{}',
  add column merged_into         uuid    references complaints(complaint_id);

create index on complaints (duplicate_status);
```

- [ ] **Step 2: Verify columns exist**

In Supabase Table Editor, open `complaints` and confirm the three new columns appear with correct types. Run:

```sql
select complaint_id, duplicate_status, duplicate_of, merged_into
from complaints
limit 1;
```

Expected: query succeeds (no error), values are null / `{}` / null for existing rows.

---

## Task 2: `duplicate_service.py`

**Files:**
- Create: `backend/app/services/duplicate_service.py`

**Interfaces:**
- Consumes: `get_supabase()` from `app.db.supabase_client`
- Produces: `detect_cross_channel_duplicates(complaint_id: str) -> None`

- [ ] **Step 1: Create the file**

```python
"""
Cross-channel duplicate detection service.

After a complaint's embedding is stored, call detect_cross_channel_duplicates()
to flag semantically similar complaints from different channels.
Threshold: cosine similarity >= 0.85.
"""

import logging
from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85


def detect_cross_channel_duplicates(complaint_id: str) -> None:
    """
    Query pgvector for complaints similar to complaint_id (cosine similarity >= 0.85)
    filed on a different channel. Flag both sides as 'possible_duplicate' and
    append each other's ID to duplicate_of[].

    Skips complaints that are already merged (duplicate_status = 'merged').
    Safe to call multiple times — uses set logic to avoid duplicate entries in the array.
    """
    supabase = get_supabase()

    # Fetch the complaint's embedding and channel
    own = (
        supabase.table("complaints")
        .select("complaint_id, channel, embedding")
        .eq("complaint_id", complaint_id)
        .execute()
    )
    if not own.data:
        logger.warning("[DEDUP] complaint %s not found", complaint_id)
        return

    row = own.data[0]
    embedding = row.get("embedding")
    channel = row.get("channel")

    if not embedding:
        logger.info("[DEDUP] complaint %s has no embedding yet — skipping", complaint_id)
        return

    # pgvector cosine similarity query — returns complaints within threshold
    # Exclude self and already-merged complaints
    # Supabase RPC: complaints must have a match_complaints function OR
    # use the raw vector operators via .rpc()
    try:
        hits = supabase.rpc(
            "match_cross_channel_complaints",
            {
                "query_embedding": embedding,
                "match_threshold": SIMILARITY_THRESHOLD,
                "match_count": 10,
                "exclude_id": complaint_id,
                "exclude_channel": channel,
            },
        ).execute()
    except Exception as exc:
        logger.error("[DEDUP] pgvector RPC failed for %s: %s", complaint_id, exc)
        return

    similar = [
        h for h in (hits.data or [])
        if h.get("duplicate_status") != "merged"
    ]

    if not similar:
        logger.info("[DEDUP] no cross-channel duplicates found for %s", complaint_id)
        return

    similar_ids = [h["complaint_id"] for h in similar]
    logger.info("[DEDUP] %s flagged as possible duplicate of %s", complaint_id, similar_ids)

    # Flag the new complaint
    supabase.table("complaints").update({
        "duplicate_status":    "possible_duplicate",
        "duplicate_of": similar_ids,
    }).eq("complaint_id", complaint_id).execute()

    # Flag each similar complaint (append this complaint_id to their array)
    for hit in similar:
        existing_ids: list = hit.get("duplicate_of") or []
        if complaint_id not in existing_ids:
            supabase.table("complaints").update({
                "duplicate_status":    "possible_duplicate",
                "duplicate_of": existing_ids + [complaint_id],
            }).eq("complaint_id", hit["complaint_id"]).execute()
```

- [ ] **Step 2: Create the Supabase RPC function**

Run in Supabase SQL editor:

```sql
create or replace function match_cross_channel_complaints(
  query_embedding   vector(512),
  match_threshold   float,
  match_count       int,
  exclude_id        text,
  exclude_channel   text
)
returns table (
  complaint_id         text,
  channel              text,
  cif_id               uuid,
  duplicate_status     text,
  duplicate_of  uuid[],
  similarity           float
)
language sql stable
as $$
  select
    c.complaint_id,
    c.channel,
    c.cif_id,
    c.duplicate_status,
    c.duplicate_of,
    1 - (c.embedding <=> query_embedding) as similarity
  from complaints c
  where
    c.complaint_id  <> exclude_id
    and c.channel   <> exclude_channel
    and c.duplicate_status is distinct from 'merged'
    and c.embedding is not null
    and 1 - (c.embedding <=> query_embedding) >= match_threshold
  order by c.embedding <=> query_embedding
  limit match_count;
$$;
```

- [ ] **Step 3: Verify the RPC works**

In Supabase SQL editor:

```sql
-- Should return empty rows (no data yet) without error
select * from match_cross_channel_complaints(
  '[0.1, 0.2, ...]'::vector(512),  -- replace with any 512-dim vector
  0.85,
  10,
  'CMP-00000000',
  'email'
);
```

Expected: query executes without error, returns 0 rows.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/duplicate_service.py
git commit -m "feat: add cross-channel duplicate detection service"
```

---

## Task 3: Duplicates API Router

**Files:**
- Create: `backend/app/api/v1/routes/duplicates.py`

**Interfaces:**
- Consumes: `get_supabase()` from `app.db.supabase_client`
- Produces:
  - `POST /api/v1/duplicates/merge` — body `MergeRequest`, returns `{"status": "merged", "primary_id": str, "secondary_id": str}`
  - `POST /api/v1/duplicates/{complaint_id}/confirm-same-person` — returns `{"status": "confirmed", "complaint_id": str}`

- [ ] **Step 1: Create the router file**

```python
"""
Duplicate complaint management endpoints.

POST /merge                       — agent confirms merge (primary wins, secondary hidden)
POST /{id}/confirm-same-person    — agent unlocks merge for different-CIF pairs
"""

import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


class MergeRequest(BaseModel):
    primary_id: str
    secondary_id: str


@router.post(
    "/merge",
    summary="Merge secondary complaint into primary (agent action)",
    status_code=status.HTTP_200_OK,
)
def merge_complaints(body: MergeRequest):
    """
    Agent selects which complaint is primary. Secondary gets merged_into set
    and duplicate_status='merged'. It will no longer appear in the main table.

    Rules:
    - Same CIF: merge allowed immediately
    - Different CIF: both must already have duplicate_status='confirmed_duplicate'
    """
    supabase = get_supabase()

    primary = supabase.table("complaints").select(
        "complaint_id, cif_id, duplicate_status"
    ).eq("complaint_id", body.primary_id).execute()

    secondary = supabase.table("complaints").select(
        "complaint_id, cif_id, duplicate_status"
    ).eq("complaint_id", body.secondary_id).execute()

    if not primary.data:
        raise HTTPException(status_code=404, detail=f"Primary complaint {body.primary_id} not found")
    if not secondary.data:
        raise HTTPException(status_code=404, detail=f"Secondary complaint {body.secondary_id} not found")

    p = primary.data[0]
    s = secondary.data[0]

    # Enforce same-person confirmation for different-CIF pairs
    same_cif = (p.get("cif_id") and p.get("cif_id") == s.get("cif_id"))
    if not same_cif:
        if s.get("duplicate_status") != "confirmed_duplicate" or p.get("duplicate_status") != "confirmed_duplicate":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Different-CIF merge requires confirm-same-person on both complaints first.",
            )

    # Soft-hide the secondary
    supabase.table("complaints").update({
        "merged_into":      body.primary_id,
        "duplicate_status": "merged",
    }).eq("complaint_id", body.secondary_id).execute()

    logger.info("[DEDUP] Merged %s into %s", body.secondary_id, body.primary_id)
    return {"status": "merged", "primary_id": body.primary_id, "secondary_id": body.secondary_id}


@router.post(
    "/{complaint_id}/confirm-same-person",
    summary="Agent confirms two different-CIF complaints are from the same person",
    status_code=status.HTTP_200_OK,
)
def confirm_same_person(complaint_id: str):
    """
    Sets duplicate_status='confirmed_duplicate' on this complaint and all
    complaints listed in its duplicate_of[] that have a different cif_id.
    This unlocks the merge button on the frontend.
    """
    supabase = get_supabase()

    own = supabase.table("complaints").select(
        "complaint_id, cif_id, duplicate_of"
    ).eq("complaint_id", complaint_id).execute()

    if not own.data:
        raise HTTPException(status_code=404, detail=f"Complaint {complaint_id} not found")

    row = own.data[0]
    own_cif = row.get("cif_id")
    related_ids: list = row.get("duplicate_of") or []

    # Mark this complaint confirmed
    supabase.table("complaints").update({
        "duplicate_status": "confirmed_duplicate"
    }).eq("complaint_id", complaint_id).execute()

    # Mark related complaints with different CIF confirmed
    for rel_id in related_ids:
        rel = supabase.table("complaints").select(
            "complaint_id, cif_id"
        ).eq("complaint_id", str(rel_id)).execute()

        if rel.data and rel.data[0].get("cif_id") != own_cif:
            supabase.table("complaints").update({
                "duplicate_status": "confirmed_duplicate"
            }).eq("complaint_id", str(rel_id)).execute()

    logger.info("[DEDUP] confirm-same-person: %s and related %s", complaint_id, related_ids)
    return {"status": "confirmed", "complaint_id": complaint_id}
```

- [ ] **Step 2: Register router in `__init__.py`**

Open `backend/app/api/v1/__init__.py`. Add the import and include:

At the top imports block, add:
```python
    duplicates,
```

After the `clusters` router block at the bottom, add:
```python
api_v1_router.include_router(
    duplicates.router,
    prefix="/duplicates",
    tags=["Duplicates"],
    **_PROTECTED,
)
```

- [ ] **Step 3: Verify routes appear in docs**

Start the backend: `uvicorn app.main:app --reload --port 8000`

Open `http://localhost:8000/docs` — confirm "Duplicates" tag appears with two endpoints:
- `POST /api/v1/duplicates/merge`
- `POST /api/v1/duplicates/{complaint_id}/confirm-same-person`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/routes/duplicates.py backend/app/api/v1/__init__.py
git commit -m "feat: add duplicate merge and confirm-same-person API endpoints"
```

---

## Task 4: Wire Detection into Pipeline

**Files:**
- Modify: `backend/app/api/v1/routes/pipeline.py` — lines 76-77 (after `build_clusters()`)

**Interfaces:**
- Consumes: `detect_cross_channel_duplicates(complaint_id: str)` from `app.services.duplicate_service`
- Produces: detection runs automatically after every pipeline completion

- [ ] **Step 1: Add the import**

At the top of `pipeline.py`, after the existing `from app.services.cluster_builder import build_clusters` line, add:

```python
from app.services.duplicate_service import detect_cross_channel_duplicates
```

- [ ] **Step 2: Call detect after `build_clusters()`**

In the `run_pipeline` function, after the `await build_clusters()` call (line ~77), add:

```python
        # ── Cross-channel duplicate detection ─────────────────────────────────
        # Runs after embedding is committed to DB by the pipeline.
        # Non-blocking: errors are logged but do not fail the pipeline response.
        try:
            detect_cross_channel_duplicates(complaint_id)
        except Exception as dedup_exc:
            logger.warning("[DEDUP] Detection failed for %s: %s", complaint_id, dedup_exc)
```

- [ ] **Step 3: Verify no startup error**

Restart backend: `uvicorn app.main:app --reload --port 8000`

Expected: server starts cleanly, no ImportError in logs.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/routes/pipeline.py
git commit -m "feat: call detect_cross_channel_duplicates after pipeline completion"
```

---

## Task 5: Frontend Types and API Methods

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces:
  - `ApiComplaint.duplicate_status?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged'`
  - `ApiComplaint.duplicate_of?: string[]`
  - `ApiComplaint.merged_into?: string | null`
  - `api.duplicates.merge(primaryId: string, secondaryId: string): Promise<{status: string, primary_id: string, secondary_id: string}>`
  - `api.duplicates.confirmSamePerson(complaintId: string): Promise<{status: string, complaint_id: string}>`

- [ ] **Step 1: Add fields to `ApiComplaint` interface**

In `frontend/src/lib/api.ts`, find the `ApiComplaint` interface and add:

```typescript
  duplicate_status?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  duplicate_of?: string[];
  merged_into?: string | null;
```

- [ ] **Step 2: Add `duplicates` namespace to the `api` object**

At the end of the `api` object (before the closing `}`), add:

```typescript
  duplicates: {
    merge: async (primaryId: string, secondaryId: string) => {
      const res = await fetch('/api/v1/duplicates/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primary_id: primaryId, secondary_id: secondaryId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Merge failed');
      }
      return res.json() as Promise<{ status: string; primary_id: string; secondary_id: string }>;
    },

    confirmSamePerson: async (complaintId: string) => {
      const res = await fetch(`/api/v1/duplicates/${complaintId}/confirm-same-person`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Confirm failed');
      }
      return res.json() as Promise<{ status: string; complaint_id: string }>;
    },
  },
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd frontend && npm run build
```

Expected: exits 0, no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add duplicate types and API methods to api.ts"
```

---

## Task 6: Complaint Table — Amber Badge and Resolve Button

**Files:**
- Modify: `frontend/src/components/ComplaintsTab.tsx`

**Interfaces:**
- Consumes: `ApiComplaint.duplicate_status`, `ApiComplaint.duplicate_of` from Task 5
- Produces: amber "Duplicate?" badge on flagged rows, inline "Resolve" button that opens merge modal (modal built in Task 7)

- [ ] **Step 1: Locate the complaint row rendering**

Open `frontend/src/components/ComplaintsTab.tsx`. Find where individual complaint rows are rendered — look for the JSX that maps over complaints and renders a `<tr>` or card per complaint.

- [ ] **Step 2: Add the amber badge**

In the row's status/badge cell, after existing status badges, add:

```tsx
{complaint.duplicate_status && complaint.duplicate_status !== 'merged' && (
  <span className="ml-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 border border-amber-300">
    Duplicate?
  </span>
)}
```

- [ ] **Step 3: Add the Resolve button**

In the row's actions cell (where existing action buttons live), add:

```tsx
{complaint.duplicate_status && complaint.duplicate_status !== 'merged' && (
  <button
    onClick={() => onOpenMergeModal(complaint)}
    className="text-xs px-2 py-1 rounded border border-amber-400 text-amber-700 hover:bg-amber-50"
  >
    Resolve
  </button>
)}
```

The `onOpenMergeModal` handler is state you'll add:

```tsx
const [mergeTarget, setMergeTarget] = useState<ApiComplaint | null>(null);

const onOpenMergeModal = (complaint: ApiComplaint) => setMergeTarget(complaint);
const onCloseMergeModal = () => setMergeTarget(null);
```

And render the modal (from Task 7) at the bottom of the component:

```tsx
{mergeTarget && (
  <MergeModal
    complaint={mergeTarget}
    onClose={onCloseMergeModal}
    onMerged={() => { onCloseMergeModal(); refetch(); }}
  />
)}
```

(`refetch` is whatever function the component uses to reload the complaints list.)

- [ ] **Step 4: Filter merged complaints from the table**

In the array passed to the table renderer, exclude merged complaints:

```tsx
const visibleComplaints = complaints.filter(c => c.duplicate_status !== 'merged');
```

Use `visibleComplaints` instead of `complaints` in the table map.

- [ ] **Step 5: Verify visually**

Start the frontend: `npm run dev`. Open the Complaints tab. Confirm:
- No visual regression on normal complaint rows
- TypeScript compiles cleanly (no red squiggles)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ComplaintsTab.tsx
git commit -m "feat: show duplicate badge and resolve button in complaints table"
```

---

## Task 7: Merge Modal and Agent Desk Banner

**Files:**
- Modify: `frontend/src/components/agent/AgentDeskTab.tsx`

**Interfaces:**
- Consumes:
  - `ApiComplaint.duplicate_status`, `duplicate_of`, `merged_into`, `cif_id` from Task 5
  - `api.duplicates.merge()`, `api.duplicates.confirmSamePerson()` from Task 5
- Produces:
  - `MergeModal` component (used by Task 6's `ComplaintsTab` and by Agent Desk detail view)
  - Duplicate banner in the complaint detail/case modal

- [ ] **Step 1: Add the duplicate banner in the detail view**

In `AgentDeskTab.tsx`, in the case modal section where `summary?.identity_status` badges already live, add below those badges:

```tsx
{/* Cross-channel duplicate banner */}
{summary?.duplicate_status && summary.duplicate_status !== 'merged' && (
  <DuplicateBanner
    complaintId={complaintId}
    duplicateStatus={summary.duplicate_status}
    crossDuplicateIds={summary.duplicate_of ?? []}
    ownCifId={summary.cif_id ?? null}
    onActionComplete={refetch}
  />
)}
```

- [ ] **Step 2: Build the `DuplicateBanner` component inline**

Above the main component export in `AgentDeskTab.tsx`, add:

```tsx
interface DuplicateBannerProps {
  complaintId: string;
  duplicateStatus: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  crossDuplicateIds: string[];
  ownCifId: string | null;
  onActionComplete: () => void;
}

function DuplicateBanner({
  complaintId,
  duplicateStatus,
  crossDuplicateIds,
  ownCifId,
  onActionComplete,
}: DuplicateBannerProps) {
  const [relatedComplaints, setRelatedComplaints] = React.useState<ApiComplaint[]>([]);
  const [showMergeModal, setShowMergeModal] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);

  React.useEffect(() => {
    if (!crossDuplicateIds.length) return;
    // Fetch the related complaint records to get their cif_ids and channels
    Promise.all(
      crossDuplicateIds.map(id =>
        api.complaints.getById(id).catch(() => null)
      )
    ).then(results => setRelatedComplaints(results.filter(Boolean) as ApiComplaint[]));
  }, [crossDuplicateIds]);

  const allSameCif = relatedComplaints.every(r => r.cif_id === ownCifId);
  const canMerge = duplicateStatus === 'confirmed_duplicate' || allSameCif;

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await api.duplicates.confirmSamePerson(complaintId);
      onActionComplete();
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
      <p className="text-xs font-semibold text-amber-800 mb-1">
        Possible duplicate complaint(s) detected
      </p>
      <div className="space-y-1">
        {relatedComplaints.map(r => {
          const diffCif = r.cif_id !== ownCifId;
          return (
            <div key={r.complaint_id} className="flex items-center gap-2 text-xs text-amber-700">
              {diffCif && (
                <span className="font-mono text-red-600">CIF: {r.cif_id?.slice(0, 8)}…</span>
              )}
              <span className="font-mono">{r.complaint_id}</span>
              <span className="text-amber-500">· {r.channel}</span>
              <a
                href={`#complaint-${r.complaint_id}`}
                className="underline text-sky-600 hover:text-sky-800"
              >
                View
              </a>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-2">
        {!allSameCif && duplicateStatus === 'possible_duplicate' && (
          <button
            onClick={handleConfirm}
            disabled={confirming}
            className="text-xs px-2 py-1 rounded border border-amber-500 text-amber-800 hover:bg-amber-100 disabled:opacity-50"
          >
            {confirming ? 'Confirming…' : 'Confirm same person'}
          </button>
        )}
        {canMerge && (
          <button
            onClick={() => setShowMergeModal(true)}
            className="text-xs px-2 py-1 rounded bg-amber-500 text-white hover:bg-amber-600"
          >
            Merge
          </button>
        )}
      </div>
      {showMergeModal && relatedComplaints.length > 0 && (
        <MergeModal
          complaint={{ complaint_id: complaintId, cif_id: ownCifId } as ApiComplaint}
          relatedComplaint={relatedComplaints[0]}
          onClose={() => setShowMergeModal(false)}
          onMerged={() => { setShowMergeModal(false); onActionComplete(); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Build the `MergeModal` component**

Add below `DuplicateBanner` in the same file:

```tsx
interface MergeModalProps {
  complaint: ApiComplaint;
  relatedComplaint?: ApiComplaint;
  onClose: () => void;
  onMerged: () => void;
}

function MergeModal({ complaint, relatedComplaint, onClose, onMerged }: MergeModalProps) {
  const [merging, setMerging] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleMerge = async (primaryId: string, secondaryId: string) => {
    setMerging(true);
    setError(null);
    try {
      await api.duplicates.merge(primaryId, secondaryId);
      onMerged();
    } catch (e: any) {
      setError(e.message || 'Merge failed');
    } finally {
      setMerging(false);
    }
  };

  const other = relatedComplaint;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl mx-4 p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-4">
          Merge Duplicate Complaints
        </h2>
        {error && (
          <div className="mb-3 rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          {[complaint, other].map((c, i) => c && (
            <div key={c.complaint_id} className="border rounded-lg p-3 space-y-1">
              <p className="text-xs font-mono text-gray-500">{c.complaint_id}</p>
              <p className="text-xs text-gray-400">Channel: {c.channel}</p>
              <p className="text-xs text-gray-400">CIF: {c.cif_id?.slice(0, 8) ?? 'N/A'}…</p>
              <p className="text-xs text-gray-700 line-clamp-4 mt-1">
                {(c as any).masked_text || (c as any).complaint_text || '—'}
              </p>
              <button
                disabled={merging}
                onClick={() => handleMerge(
                  c.complaint_id,
                  c === complaint ? (other?.complaint_id ?? '') : complaint.complaint_id,
                )}
                className="mt-2 w-full text-xs px-3 py-1.5 rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {merging ? 'Merging…' : 'Make Primary'}
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={onClose}
          className="mt-4 text-xs text-gray-400 hover:text-gray-600"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add `api.complaints.getById` if it doesn't exist**

In `frontend/src/lib/api.ts`, inside the `complaints` namespace, add:

```typescript
    getById: async (complaintId: string): Promise<ApiComplaint> => {
      const res = await fetch(`/api/v1/complaints/${complaintId}`);
      if (!res.ok) throw new Error('Complaint not found');
      return res.json();
    },
```

(Check if a similar method already exists — if so, use that name in `DuplicateBanner` instead.)

- [ ] **Step 5: Run TypeScript check**

```bash
cd frontend && npm run build
```

Expected: exits 0, no type errors.

- [ ] **Step 6: Verify visually**

Start both servers. Open Agent Desk:
- Normal complaints: no banner visible
- A complaint with `duplicate_status = 'possible_duplicate'`: amber banner appears, related IDs shown, View links work
- Same-CIF pair: Merge button active immediately
- Diff-CIF pair: "Confirm same person" button shown; after clicking, both flip to `confirmed_duplicate` and Merge button appears
- Clicking Make Primary: secondary disappears from table, modal closes

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/agent/AgentDeskTab.tsx frontend/src/lib/api.ts
git commit -m "feat: duplicate banner and merge modal in Agent Desk and complaint table"
```

---

## Verification Checklist

- [ ] File complaint from email, then near-identical text from WhatsApp (same CIF) → both show "Duplicate?" badge in table
- [ ] Open either complaint's detail in Agent Desk → amber banner with related complaint ID, channel, and "Merge" button
- [ ] Click "Make Primary" on either side → secondary disappears from table, primary remains
- [ ] File similar complaints from two different CIF customers → diff-CIF banner with CIF prefix shown, Merge locked
- [ ] Click "Confirm same person" → both flip `confirmed_duplicate`, Merge button appears
- [ ] File complaint with < 0.85 similarity → no flag, no badge
- [ ] `npm run build` exits 0 (TypeScript clean)
- [ ] `uvicorn app.main:app --reload` starts without error
