# Merged Complaints Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the All Complaints table so parent complaints show an expandable accordion revealing all merged children beneath them.

**Architecture:** Remove the `.filter()` that hides merged complaints; group them into a `mergedChildrenMap` in `ComplaintsTab`; pass the map to `ComplaintsTable` which renders a chevron toggle column and an animated expanded panel (`MergedChildrenPanel`) inline after each parent row.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React icons

## Global Constraints

- Zero backend changes — frontend-only.
- No new badge components — reuse `StatusBadge`, `ChannelBadge`.
- No nested `<table>` inside the expanded row — use a `<div>` with flex/grid layout.
- `StatusBadge` receives `"Resolved"` unchanged; a separate "Merged" pill sits beside it.
- Animation: `max-height` transition, 150–200 ms, Tailwind utility classes only.
- Chevron column: fixed `w-8`, empty spacer for rows with no children (keeps column alignment).
- Row click (`onSelect`) unchanged; only the chevron toggles expand/collapse.
- "Filed" column in child rows uses the complaint's `date` + `time` fields (no `merged_at`).

---

## File Map

| File | Change |
|------|--------|
| `frontend/src/types/index.ts` | Add `mergedInto?: string` to `Complaint` interface |
| `frontend/src/components/complaints/ComplaintsTab.tsx` | Remove merged filter; add `mergedInto` to `apiToFrontend`; build `mergedChildrenMap`; pass to `ComplaintsTable` |
| `frontend/src/components/complaints/ComplaintsTable.tsx` | Add `mergedChildrenMap` prop, `expandedRows` state, chevron column, `Merged (N)` badge, expanded `<tr>`, `MergedChildrenPanel` sub-component |

---

## Task 1: Add `mergedInto` to the Complaint type

**Files:**
- Modify: `frontend/src/types/index.ts` (lines 200–202)

**Interfaces:**
- Produces: `Complaint.mergedInto?: string` — used by Task 2 to populate from API data and Task 3 to identify parent vs child rows.

- [ ] **Step 1: Add the field**

Open `frontend/src/types/index.ts`. The `Complaint` interface currently ends at line 202:
```typescript
  duplicateStatus?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  duplicateOf?: string[];
}
```
Change it to:
```typescript
  duplicateStatus?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  duplicateOf?: string[];
  mergedInto?: string;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors related to `mergedInto`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add mergedInto field to Complaint type"
```

---

## Task 2: Map `merged_into` in `apiToFrontend` and build `mergedChildrenMap`

**Files:**
- Modify: `frontend/src/components/complaints/ComplaintsTab.tsx`

**Interfaces:**
- Consumes: `ApiComplaint.merged_into?: string | null` (already in `api.ts`), `Complaint.mergedInto?: string` (Task 1)
- Produces:
  - `mergedChildrenMap: Map<string, Complaint[]>` — keyed by parent complaint ID, value is array of child `Complaint` objects. Exported as a prop to `ComplaintsTable`.
  - `visibleComplaints: Complaint[]` — only complaints where `mergedInto` is undefined (parents + standalones).

- [ ] **Step 1: Add `mergedInto` mapping in `apiToFrontend`**

In `ComplaintsTab.tsx`, the `apiToFrontend` function returns an object at lines 57–122. Add one field to the return value after `duplicateOf`:

```typescript
    duplicateStatus: c.duplicate_status as Complaint['duplicateStatus'],
    duplicateOf: c.duplicate_of ?? [],
    mergedInto: c.merged_into ?? undefined,
```

- [ ] **Step 2: Remove the merged filter and build `mergedChildrenMap`**

Find lines 147–151:
```typescript
  const complaints: Complaint[] = usingApi
    ? apiData.complaints
        .filter((c) => c.duplicate_status !== 'merged')
        .map(apiToFrontend)
    : COMPLAINTS;
```

Replace with:
```typescript
  const allComplaints: Complaint[] = usingApi
    ? apiData.complaints.map(apiToFrontend)
    : COMPLAINTS;

  // Group merged children under their parent
  const mergedChildrenMap = new Map<string, Complaint[]>();
  for (const c of allComplaints) {
    if (c.mergedInto) {
      const existing = mergedChildrenMap.get(c.mergedInto) ?? [];
      mergedChildrenMap.set(c.mergedInto, [...existing, c]);
    }
  }

  // Only parent/standalone complaints appear as top-level rows
  const complaints: Complaint[] = allComplaints.filter((c) => !c.mergedInto);
```

- [ ] **Step 3: Pass `mergedChildrenMap` to `ComplaintsTable`**

Find the `<ComplaintsTable>` usage (lines 275–279):
```tsx
        <ComplaintsTable
          complaints={filtered}
          selected={enrichedSelected}
          onSelect={handleSelect}
        />
```

Replace with:
```tsx
        <ComplaintsTable
          complaints={filtered}
          selected={enrichedSelected}
          onSelect={handleSelect}
          mergedChildrenMap={mergedChildrenMap}
        />
```

Note: TypeScript will error here until Task 3 adds the prop to `ComplaintsTable`. That's expected — fix it by completing Task 3 next.

- [ ] **Step 4: Verify TypeScript (after Task 3 is done)**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/complaints/ComplaintsTab.tsx
git commit -m "feat: build mergedChildrenMap and pass to ComplaintsTable"
```

---

## Task 3: Expandable rows and `MergedChildrenPanel` in `ComplaintsTable`

**Files:**
- Modify: `frontend/src/components/complaints/ComplaintsTable.tsx`

**Interfaces:**
- Consumes: `mergedChildrenMap: Map<string, Complaint[]>` (Task 2), `Complaint.mergedInto?: string` (Task 1), `onSelect: (c: Complaint) => void` (existing)
- Produces: Expandable table rows with animated child panels. `MergedChildrenPanel` is a private sub-component in the same file.

- [ ] **Step 1: Add imports**

At the top of `ComplaintsTable.tsx`, the current imports are:
```typescript
import type { Complaint } from "../../types";
import { StatusBadge } from "../ui/StatusBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { SlaBadge } from "../ui/SlaBadge";
```

Replace with:
```typescript
import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { Complaint } from "../../types";
import { StatusBadge } from "../ui/StatusBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { SlaBadge } from "../ui/SlaBadge";
```

- [ ] **Step 2: Add `MergedChildrenPanel` sub-component**

Add this entire sub-component immediately before the `ComplaintsTable` function export (after the `HEADERS` const, before the `export function ComplaintsTable`):

```tsx
interface MergedChildrenPanelProps {
  children: Complaint[];
  isExpanded: boolean;
  onSelect: (c: Complaint) => void;
}

function MergedChildrenPanel({ children, isExpanded, onSelect }: MergedChildrenPanelProps) {
  return (
    <div
      className={`overflow-hidden transition-all duration-200 ease-in-out ${
        isExpanded ? "max-h-[600px]" : "max-h-0"
      }`}
    >
      <div className="bg-slate-50 border-t border-slate-200 px-4 pt-3 pb-4">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <svg
            className="text-indigo-400"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <span className="text-xs font-semibold text-slate-700">
            Merged Complaints ({children.length})
          </span>
          <span className="text-xs text-gray-400">
            These complaints have been merged into the parent complaint above.
          </span>
        </div>

        {/* Child rows */}
        <div className="border-l-2 border-indigo-200 pl-3 space-y-1">
          {children.map((child, idx) => {
            const isLast = idx === children.length - 1;
            return (
              <div
                key={child.id}
                className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0"
              >
                {/* Tree indicator */}
                <span className="font-mono text-xs text-gray-300 select-none flex-shrink-0">
                  {isLast ? "└──" : "├──"}
                </span>

                {/* ID — clickable */}
                <button
                  onClick={() => onSelect(child)}
                  className="text-xs font-mono font-semibold text-ub-blue hover:underline whitespace-nowrap flex-shrink-0"
                >
                  {child.id}
                </button>

                {/* Customer */}
                <span className="text-xs text-gray-700 whitespace-nowrap flex-shrink-0 min-w-[140px]">
                  {child.customer}
                </span>

                {/* Channel */}
                <span className="flex-shrink-0">
                  <ChannelBadge channel={child.channel} />
                </span>

                {/* Category */}
                <span className="text-xs text-gray-600 flex-1 min-w-0 truncate">
                  {child.category}
                </span>

                {/* Status + Merged pill */}
                <span className="flex items-center gap-1 flex-shrink-0">
                  <StatusBadge status={child.status} />
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-500 font-medium">
                    Merged
                  </span>
                </span>

                {/* Filed */}
                <span className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">
                  {child.date} {child.time}
                </span>

                {/* Actions */}
                <button
                  onClick={() => onSelect(child)}
                  className="flex-shrink-0 p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-slate-100"
                  title="Open complaint"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
                  </svg>
                </button>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <p className="mt-2 text-xs text-gray-400">
          {children.length} complaint{children.length !== 1 ? "s" : ""} merged into this parent
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update `Props` interface and add `expandedRows` state**

Replace the current `Props` interface and function signature:
```typescript
interface Props {
  complaints: Complaint[];
  selected: Complaint | null;
  onSelect: (c: Complaint) => void;
}
```
With:
```typescript
interface Props {
  complaints: Complaint[];
  selected: Complaint | null;
  onSelect: (c: Complaint) => void;
  mergedChildrenMap?: Map<string, Complaint[]>;
}
```

Replace the function opening:
```typescript
export function ComplaintsTable({ complaints, selected, onSelect }: Props) {
  return (
```
With:
```typescript
export function ComplaintsTable({ complaints, selected, onSelect, mergedChildrenMap = new Map() }: Props) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
```

- [ ] **Step 4: Update `HEADERS` to include the chevron column**

Replace:
```typescript
const HEADERS = [
  "ID",
  "Customer",
  "Channel",
  "Category / Type",
  "Status",
  "SLA",
  "",
];
```
With:
```typescript
const HEADERS = [
  "",        // chevron column
  "ID",
  "Customer",
  "Channel",
  "Category / Type",
  "Status",
  "SLA",
  "",        // duplicate flag / actions
];
```

- [ ] **Step 5: Update the `<thead>` to add fixed-width chevron header**

The current `<thead>` maps `HEADERS` uniformly. Add a `w-8` class for the first header cell. Replace the `<thead>` block:

```tsx
          <thead className="sticky top-0 z-10 bg-slate-50 border-b border-gray-100">
            <tr>
              {HEADERS.map((h, i) => (
                <th
                  key={i}
                  className={`text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap ${i === 0 ? "w-8 px-2" : ""}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
```

- [ ] **Step 6: Update the row to add chevron column, Merged badge, and expanded panel**

Replace the entire `<tbody>` block (lines 39–101) with:

```tsx
          <tbody>
            {complaints.map((c) => {
              const isSelected = selected?.id === c.id;
              const isPending = c.category === "Analysing…";
              const mergedChildren = mergedChildrenMap.get(c.id) ?? [];
              const hasChildren = mergedChildren.length > 0;
              const isExpanded = expandedRows.has(c.id);

              return (
                <>
                  <tr
                    key={c.id}
                    onClick={() => onSelect(c)}
                    className={`border-b border-gray-50 cursor-pointer transition-colors last:border-0 ${
                      isSelected ? "bg-ub-blue-light" : "hover:bg-slate-50"
                    }`}
                  >
                    {/* Chevron column — fixed w-8 */}
                    <td className="w-8 px-2 py-3">
                      {hasChildren ? (
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleExpand(c.id); }}
                          className="flex items-center justify-center w-6 h-6 rounded hover:bg-slate-200 text-gray-400"
                        >
                          {isExpanded
                            ? <ChevronDown size={14} />
                            : <ChevronRight size={14} />
                          }
                        </button>
                      ) : (
                        <div className="w-8" />
                      )}
                    </td>

                    {/* ID + Merged badge */}
                    <td className="px-4 py-3 text-xs font-mono font-semibold text-ub-blue whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {c.id}
                        {hasChildren && (
                          <span className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-100 text-indigo-700">
                            Merged ({mergedChildren.length})
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Customer */}
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-800 whitespace-nowrap text-sm">
                        {c.customer}
                      </div>
                    </td>

                    {/* Channel */}
                    <td className="px-4 py-3">
                      <ChannelBadge channel={c.channel} />
                    </td>

                    {/* Category / Type */}
                    <td className="px-4 py-3">
                      <div
                        className={`whitespace-nowrap ${isPending ? "text-xs text-slate-400 italic" : "text-sm text-gray-800"}`}
                      >
                        {c.category}
                      </div>
                      {!isPending && c.type && (
                        <div className="text-xs text-gray-400">{c.type}</div>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>

                    {/* SLA */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <SlaBadge breached={c.slaBreached} label={c.slaRemaining} />
                    </td>

                    {/* Duplicate flag */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      {c.duplicateStatus && c.duplicateStatus !== 'merged' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                          Duplicate?
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Expanded merged children panel */}
                  {hasChildren && (
                    <tr key={`${c.id}-children`}>
                      <td colSpan={HEADERS.length} className="p-0">
                        <MergedChildrenPanel
                          children={mergedChildren}
                          isExpanded={isExpanded}
                          onSelect={onSelect}
                        />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
```

- [ ] **Step 7: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors. If you see `'children' is a reserved prop` warning from React, rename the prop to `mergedItems` in both `MergedChildrenPanel`'s interface and its usage inside the expanded `<tr>`.

- [ ] **Step 8: Smoke test in the browser**

Start dev server:
```bash
cd frontend && npm run dev
```
Open http://localhost:5173, navigate to All Complaints tab.

Verify:
1. Standalone complaints (no merged children) show a blank `w-8` spacer in the first column — no shift in alignment.
2. A parent complaint with merged children shows `▶` chevron + `Merged (N)` indigo badge next to its ID.
3. Clicking the chevron expands the panel (200 ms animation) — children appear with `├──` / `└──` indicators, `StatusBadge("Resolved")` + "Merged" pill, and "Filed" date.
4. Clicking the parent row (not the chevron) opens `ComplaintDetailModal` for the parent.
5. Clicking a child complaint ID opens `ComplaintDetailModal` for the child.
6. Clicking the chevron again collapses the panel with animation.

- [ ] **Step 9: Build check**

```bash
cd frontend && npm run build
```
Expected: exit 0, no TypeScript errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/complaints/ComplaintsTable.tsx
git commit -m "feat: expandable merged complaints hierarchy in complaints table"
```
