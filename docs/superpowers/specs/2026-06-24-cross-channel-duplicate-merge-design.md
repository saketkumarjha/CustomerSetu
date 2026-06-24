# Cross-Channel Duplicate Complaint Merge — Design Spec

**Date:** 2026-06-24  
**Status:** Approved

---

## Context

The identity resolution system (CIF) already links the same customer's complaints across channels. This feature extends that by detecting when the same customer (or even different customers) filed semantically identical complaints from different channels, flagging them for agent review, and allowing agents to merge the secondary into the primary.

LangGraph pipeline is not touched. All duplicate detection and merge logic lives outside the pipeline.

---

## Scope

- Detect cross-channel duplicate complaints with cosine similarity ≥ 0.85 (pgvector)
- Detection is codebase-wide — not scoped to same-CIF only
- Agent decides which complaint is primary; system does not auto-merge
- Secondary complaint is soft-hidden on merge (`merged_into` set, disappears from table)
- Different-CIF matches are shown with a hyperlink and require an explicit "Confirm same person" step before merge is unlocked

---

## Database

Two new columns on `complaints`:

```sql
alter table complaints
  add column duplicate_status text check (
    duplicate_status in ('possible_duplicate', 'confirmed_duplicate', 'merged')
  ),
  add column duplicate_of     uuid[]  not null default '{}',
  add column merged_into      uuid    references complaints(complaint_id);
```

- `duplicate_status`: null means no duplicate detected; `possible_duplicate` = flagged by detector; `confirmed_duplicate` = agent confirmed diff-CIF match is same person; `merged` = secondary after agent merge
- `duplicate_of`: array of complaint IDs that are similar to this one
- `merged_into`: set on the secondary complaint when agent confirms merge; primary keeps its own status

---

## New Service: `backend/app/services/duplicate_service.py`

Single public function:

```python
def detect_cross_channel_duplicates(complaint_id: str) -> None
```

**Logic:**
1. Fetch the complaint's embedding from the `complaints` table
2. Run pgvector cosine similarity query against all other non-merged complaints: `similarity ≥ 0.85`, exclude self, limit 10
3. For each hit with a different `channel` value:
   - Append `complaint_id` to hit's `duplicate_of[]`, set `duplicate_status = 'possible_duplicate'` (if not already merged)
   - Append hit's ID to this complaint's `duplicate_of[]`, set `duplicate_status = 'possible_duplicate'`
4. Same-CIF and different-CIF matches are stored identically — the distinction is read-time only (compare `cif_id` fields)

**When it runs:** Called from `backend/app/api/v1/routes/pipeline.py` after the pipeline run completes and the embedding is confirmed stored. No LangGraph changes.

---

## API Endpoints

### `POST /api/v1/complaints/merge`

Body:
```json
{ "primary_id": "<uuid>", "secondary_id": "<uuid>" }
```

Server-side rules:
- Same CIF → merge allowed immediately
- Different CIF → only allowed if `duplicate_status = 'confirmed_duplicate'` on both; otherwise returns 403
- On success: sets `merged_into = primary_id` and `duplicate_status = 'merged'` on secondary

### `POST /api/v1/complaints/{id}/confirm-same-person`

No body required. Sets `duplicate_status = 'confirmed_duplicate'` on both the target complaint and all complaints in its `duplicate_of[]` array that have a different `cif_id`. Unlocks the merge button on the frontend.

---

## Frontend

### Complaint Table

- Rows where `duplicate_status` is non-null show an amber **"Duplicate?"** badge
- An inline **"Resolve"** button appears on those rows → opens the merge modal

### Detail View Banner

**Same CIF** (merge immediately available):
> Possible duplicate of `CMP-XXXX` · same customer · different channel **[Merge]**

**Different CIF** (merge locked):
> Similar complaint from CIF `<cif_id_short>` → `CMP-XXXX` **[View]** · Confirm same person to enable merge **[Confirm]**

Clicking **[View]** navigates to the linked complaint's detail.  
Clicking **[Confirm]** calls `confirm-same-person`, then re-renders with the merge button active.

### Merge Modal

- Side-by-side view: left = complaint A, right = complaint B
- Each side shows: channel, submitted_at, complaint text (truncated), CIF ID
- **"Make Primary"** button under each side
- Confirming calls `POST /api/v1/complaints/merge`
- On success: secondary disappears from the table; primary's detail view gains a "Merged from CMP-XXXX (via {channel})" note

---

## Files Modified / Created

| Action | File |
|--------|------|
| **Create** | `backend/app/services/duplicate_service.py` |
| **Create** | `backend/app/api/v1/routes/duplicates.py` |
| **Modify** | `backend/app/api/v1/__init__.py` — register duplicates router |
| **Modify** | `backend/app/api/v1/routes/pipeline.py` — call `detect_cross_channel_duplicates` post-run |
| **Modify** | `frontend/src/lib/api.ts` — add duplicate fields to `ApiComplaint`, add merge/confirm API methods |
| **Modify** | `frontend/src/components/ComplaintsTab.tsx` — amber badge + Resolve button in table |
| **Modify** | `frontend/src/components/agent/AgentDeskTab.tsx` — duplicate banner in detail view |
| **SQL** | Run in Supabase dashboard (two new columns on complaints) |

---

## Verification

1. File same complaint text from email and WhatsApp (same CIF) → both flagged `possible_duplicate`, amber badge appears in table
2. Agent opens detail → sees same-CIF banner with Merge button → picks primary → secondary disappears from table
3. File similar complaint from two different customers (different CIF) → both flagged, diff-CIF banner shown with View link and Confirm button
4. Agent clicks Confirm → both flip to `confirmed_duplicate` → Merge button unlocks → agent merges
5. File complaint with similarity < 0.85 → no flag, no badge
