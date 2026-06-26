# Merged Complaints Hierarchy in All Complaints Table

**Date:** 2026-06-25
**Status:** Approved

---

## Context

When duplicate complaints are merged into a parent complaint, merged (child) complaints are currently filtered out of the All Complaints table entirely. They appear nowhere visible to the agent. This makes it impossible to understand that multiple complaints from the same customer have been consolidated — the parent row gives no indication that children exist, and the children are invisible.

The goal is to make parent complaints expandable, showing all merged children as an indented hierarchy beneath the parent row, matching the Jira/Linear/Datadog pattern of inline hierarchical data.

---

## Approach

**Frontend-only grouping from the existing list call (Approach A).** Remove the `.filter()` that hides merged complaints. Group all complaints on the frontend into a `mergedChildrenMap`. No backend changes. No new API endpoints.

---

## Data Layer — `ComplaintsTab`

**File:** `frontend/src/components/complaints/ComplaintsTab.tsx`

1. Remove the `.filter((c) => c.duplicate_status !== 'merged')` line that currently hides merged complaints.
2. Map all complaints (including merged ones) through `apiToFrontend()`.
3. Build two derived structures from the mapped list:
   - `mergedChildrenMap: Map<string, Complaint[]>` — keyed by parent complaint ID (`ApiComplaint.merged_into`), value is the array of child `Complaint` objects.
   - `visibleComplaints: Complaint[]` — complaints where `ApiComplaint.merged_into` is null (true parents and standalone complaints only).
4. Pass `mergedChildrenMap` as a new prop to `ComplaintsTable`.

**Type change — `frontend/src/types/index.ts`:**
Add one field to the `Complaint` interface:
```typescript
mergedInto?: string;   // mapped from ApiComplaint.merged_into
```
Also add the mapping in `apiToFrontend()`:
```typescript
mergedInto: c.merged_into ?? undefined,
```

---

## ComplaintsTable — Expandable Row Structure

**File:** `frontend/src/components/complaints/ComplaintsTable.tsx`

### New prop
```typescript
mergedChildrenMap: Map<string, Complaint[]>
```

### New state
```typescript
const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
const toggleExpand = (id: string) =>
  setExpandedRows(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
```

### Chevron column (first column, fixed `w-8`)
- Complaints with children in `mergedChildrenMap`: render `ChevronRight` (collapsed) or `ChevronDown` (expanded), `size={14}`, `text-gray-400`. `onClick={e => { e.stopPropagation(); toggleExpand(c.id); }}`.
- Complaints without children: render an empty `<div className="w-8" />` spacer. Columns stay perfectly aligned.

### Merged badge (inline after complaint ID)
When `mergedChildrenMap.get(c.id)?.length > 0`, render:
```tsx
<span className="ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-100 text-indigo-700">
  Merged ({count})
</span>
```

### Expanded panel — `<tr>` with full colspan
Immediately after the parent `<tr>`, insert:
```tsx
{isExpanded && (
  <tr>
    <td colSpan={HEADERS.length + 1}>  {/* +1 for chevron column */}

      <MergedChildrenPanel
        children={mergedChildrenMap.get(c.id)!}
        onSelect={onSelect}
        isExpanded={isExpanded}
      />
    </td>
  </tr>
  
)}
```

### Row click — unchanged
`onClick={() => onSelect(c)}` on the parent row continues to open the detail modal. The chevron click uses `e.stopPropagation()` to avoid triggering `onSelect`.

---

## MergedChildrenPanel Sub-component

Co-located in `ComplaintsTable.tsx` (not a separate file — tightly coupled to table layout).

**Structure:**
```
<div> <!-- outer wrapper, animated via max-height transition -->
  <div> <!-- header -->
    <UsersIcon size={14} />
    "Merged Complaints (N)"
    <span class="text-gray-400">These complaints have been merged into the parent complaint above.</span>
  </div>

  <div> <!-- child rows, CSS grid matching parent column widths -->
    <!-- per child: -->
    <div class="border-l-2 border-indigo-200 pl-3">
      <span class="text-gray-400">├──</span>  (last child uses └──)
      <button onClick={() => onSelect(child)}>CMP-XXXXXX</button>  <!-- blue mono -->
      customer | ChannelBadge | category/type | StatusBadge("Resolved") + "Merged" badge | filed date+time | ⋮ actions
    </div>
  </div>

  <div> <!-- footer -->
    <span class="text-xs text-gray-400">{N} complaints merged into this parent</span>
  </div>
</div>
```

**Hierarchy indicator:**
- Thin `border-l-2 border-indigo-200` vertical line on the left edge of the expanded panel.
- Each child prefixed with `├──` (all except last) or `└──` (last child), `text-gray-300`, `font-mono text-xs`.

**Status display (no new StatusBadge values):**
```tsx
<StatusBadge status="Resolved" />
<span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-500 font-medium">
  Merged
</span>
```
`StatusBadge` is unchanged.

**"Filed" column:**
Shows the child complaint's `date` and `time` fields (from `created_at` via `apiToFrontend()`). Column header label: **Filed**. No `merged_at` field needed.

**Animation:**
```css
/* via Tailwind */
max-h-0 overflow-hidden transition-all duration-200 ease-in-out
/* when expanded: */
max-h-[600px]
```
150–200 ms expand/collapse. Controlled by `isExpanded` prop passed from the parent table row.

**Footer:**
No "View Parent Complaint" button. Footer shows only the count label: `"{N} complaints merged into this parent"`.

---

## Components Unchanged

- `ComplaintDetailModal.tsx` — no changes
- `DuplicateBanner.tsx` — no changes
- `StatusBadge.tsx` — no changes; receives existing `"Resolved"` value
- All backend files — no changes

---

## Files Modified

| File | Change |
|------|--------|
| `frontend/src/types/index.ts` | Add `mergedInto?: string` to `Complaint` |
| `frontend/src/components/complaints/ComplaintsTab.tsx` | Remove merged filter; build `mergedChildrenMap`; pass to `ComplaintsTable` |
| `frontend/src/components/complaints/ComplaintsTable.tsx` | Add chevron col, `expandedRows` state, `Merged (N)` badge, expanded `<tr>`, `MergedChildrenPanel` sub-component |

---

## Verification

1. Start the backend (`uvicorn app.main:app --reload --port 8000`).
2. Submit two complaints from the same email; merge one into the other via the Merge button in the detail modal.
3. Open the All Complaints tab.
4. Confirm the parent row shows `Merged (1)` badge and a chevron `▶`.
5. Click the chevron — expanded panel appears with the child complaint, `├──` indicator, `StatusBadge("Resolved")` + "Merged" badge, and the child's filed date.
6. Click the child complaint ID — detail modal opens for the child.
7. Click the parent row (not the chevron) — detail modal opens for the parent.
8. Click the chevron again — panel collapses with animation.
9. Confirm standalone complaints (no merged children) show no chevron and no badge, and their rows are column-aligned with parent rows.
