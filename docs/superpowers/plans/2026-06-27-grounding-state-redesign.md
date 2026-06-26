# Grounding State Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the four grounding states (Passed, Warnings Found, Skipped, Failed) explicit and reliable by fixing three backend bugs and redesigning the grounding section in the complaint detail panel.

**Architecture:** Two existing fields (`grounding_score` + `grounding_warnings`) encode all four states via a strict contract. Backend changes fix wrong sentinel values and add a normalization helper for the escalation re-run path. The UI always renders the grounding section and derives its display state purely from the two fields.

**Tech Stack:** Python 3.11 (FastAPI/LangGraph backend), React 18 + TypeScript (Vite frontend), Tailwind CSS.

## Global Constraints

- No schema changes — `grounding_score` (float | null) and `grounding_warnings` (JSONB array) are the only fields used.
- State contract: `null/[]` = Skipped; `>0.0/[]` = Passed; `>0.0/[...]` = Warnings Found; `0.0/[SYSTEM_ERROR]` = Failed.
- `GroundingWarningRow` component must not be modified.
- `ComplaintDetailModal.tsx` debug dump must not be modified.

---

### Task 1: Fix `grounding_score` sentinel in `graph.py`

**Files:**
- Modify: `backend/app/services/supervisor/graph.py:629`

**Interfaces:**
- Produces: `grounding_score = 0.0` when `grounding_node` exception handler fires, paired with existing `SYSTEM_ERROR` warning already in the except block.

- [ ] **Step 1: Open the file and locate the exception handler**

  File: `backend/app/services/supervisor/graph.py`, line 629.
  The current except block (around line 625–651) reads:
  ```python
  except Exception as e:
      # Grounding failure — flag for human review conservatively
      logger.error(...)
      grounding_score = 0.5   # ← WRONG sentinel
      warnings = [{
          "type": "SYSTEM_ERROR",
          "claim": "Grounding check failed",
          "issue": str(e),
          "suggestion": "Human agent must manually verify all claims in draft"
      }]
      overall = "VERIFY_BEFORE_SEND"
  ```

- [ ] **Step 2: Change the sentinel from `0.5` to `0.0`**

  Replace only the one line:
  ```python
  grounding_score = 0.5
  ```
  With:
  ```python
  grounding_score = 0.0
  ```

  The SYSTEM_ERROR warning structure directly below is already correct — do not touch it.

- [ ] **Step 3: Verify the change is isolated**

  Run a quick grep to confirm no other location in `graph.py` sets `grounding_score = 0.5`:
  ```bash
  grep -n "grounding_score = 0.5" backend/app/services/supervisor/graph.py
  ```
  Expected: no output.

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/services/supervisor/graph.py
  git commit -m "fix: grounding failure sentinel 0.5 → 0.0 in graph.py"
  ```

---

### Task 2: Add `_normalize_grounding_state` helper and wire it into `partial_pipeline_runner.py`

**Files:**
- Modify: `backend/app/services/partial_pipeline_runner.py`

**Interfaces:**
- Produces: `_normalize_grounding_state(score, warnings) -> tuple[float | None, list]` — used at lines ~96–97 and in the Agent 9 exception handler at lines ~114–115.

- [ ] **Step 1: Add the helper function after the imports block**

  Open `backend/app/services/partial_pipeline_runner.py`. After the last `from`/`import` line (line ~18) and before `async def run_tier_transition_pipeline`, insert:

  ```python
  def _normalize_grounding_state(
      score: float | None,
      warnings: list,
  ) -> tuple[float | None, list]:
      warnings = warnings or []

      if score is None:
          return None, []

      if score == 1.0:
          return 1.0, []

      if score == 0.0:
          has_system_error = any(
              isinstance(w, dict) and w.get("type") == "SYSTEM_ERROR"
              for w in warnings
          )
          if not has_system_error:
              warnings = [{
                  "type": "SYSTEM_ERROR",
                  "claim": "Grounding state repaired",
                  "issue": "Grounding failed but no SYSTEM_ERROR warning was present.",
                  "suggestion": "Review the draft manually.",
              }]
          return 0.0, warnings

      return score, warnings
  ```

- [ ] **Step 2: Replace the `or 0.8` fallback at lines ~96–97**

  Current code (lines 96–97):
  ```python
  grounding_score: float = original_state.get("grounding_score", 0.8) or 0.8
  grounding_warnings: list = original_state.get("grounding_warnings", []) or []
  ```

  Replace with:
  ```python
  grounding_score, grounding_warnings = _normalize_grounding_state(
      original_state.get("grounding_score"),
      original_state.get("grounding_warnings"),
  )
  ```

  Note: remove the type annotations (`float`, `list`) from these variable declarations — `_normalize_grounding_state` returns a tuple and Python will infer the types.

- [ ] **Step 3: Extend the Agent 9 exception handler at lines ~114–115**

  Current code:
  ```python
  except Exception as e:
      errors.append(f"Agent 9 (Grounding) failed at Tier {new_tier_level}: {e}")
  ```

  Replace with:
  ```python
  except Exception as e:
      errors.append(f"Agent 9 (Grounding) failed at Tier {new_tier_level}: {e}")
      grounding_score = 0.0
      grounding_warnings = [{
          "type": "SYSTEM_ERROR",
          "claim": "Grounding check failed during escalation re-run",
          "issue": str(e),
          "suggestion": "Human agent must manually verify all claims in draft",
      }]
  ```

- [ ] **Step 4: Verify the file parses**

  ```bash
  cd backend
  python -c "from app.services.partial_pipeline_runner import run_tier_transition_pipeline, _normalize_grounding_state; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 5: Quick unit-level smoke test of the helper**

  Run this in the Python REPL from `backend/` (with venv active):
  ```python
  from app.services.partial_pipeline_runner import _normalize_grounding_state

  # Skipped
  assert _normalize_grounding_state(None, []) == (None, [])
  assert _normalize_grounding_state(None, [{"type": "stale"}]) == (None, [])

  # Passed
  assert _normalize_grounding_state(1.0, []) == (1.0, [])
  assert _normalize_grounding_state(1.0, [{"stale": True}]) == (1.0, [])

  # Warnings Found
  score, warnings = _normalize_grounding_state(0.85, [{"type": "UNVERIFIABLE_CLAIM", "claim": "x", "issue": "y", "suggestion": "z"}])
  assert score == 0.85
  assert len(warnings) == 1

  # Failed — already has SYSTEM_ERROR
  score, warnings = _normalize_grounding_state(0.0, [{"type": "SYSTEM_ERROR", "claim": "c", "issue": "i", "suggestion": "s"}])
  assert score == 0.0
  assert warnings[0]["type"] == "SYSTEM_ERROR"

  # Failed — missing SYSTEM_ERROR (legacy repair)
  score, warnings = _normalize_grounding_state(0.0, [])
  assert score == 0.0
  assert warnings[0]["type"] == "SYSTEM_ERROR"
  assert warnings[0]["claim"] == "Grounding state repaired"

  print("All assertions passed")
  ```
  Expected: `All assertions passed`

- [ ] **Step 6: Commit**

  ```bash
  git add backend/app/services/partial_pipeline_runner.py
  git commit -m "fix: normalize grounding state in partial_pipeline_runner escalation path"
  ```

---

### Task 3: Redesign the grounding section in `ComplaintDetailPanel.tsx`

**Files:**
- Modify: `frontend/src/components/complaints/detail/ComplaintDetailPanel.tsx`

**Interfaces:**
- Consumes: `apiDetail.grounding_score: number | null | undefined`, `apiDetail.grounding_warnings: (string | GroundingWarningItem)[] | undefined`, `apiDetail.is_duplicate: boolean | undefined`
- Produces: Always-rendered grounding section with four distinct visual states (Skipped/Passed/Warnings/Failed)

- [ ] **Step 1: Add the two helper functions before the `ComplaintDetailPanel` component**

  In `ComplaintDetailPanel.tsx`, find the `GroundingWarningRow` function (line 27). Insert the following two helpers directly after the closing brace of `GroundingWarningRow` (after line 49), before `RouteStatusPill`:

  ```typescript
  type GroundingStatus = "skipped" | "passed" | "warnings" | "failed";

  function deriveGroundingStatus(
    score: number | null | undefined,
    warnings: (string | GroundingWarningItem)[] | undefined,
  ): GroundingStatus {
    if (score === null || score === undefined) return "skipped";
    if (
      score === 0.0 &&
      (warnings ?? []).some(
        (w) => typeof w === "object" && (w as GroundingWarningItem).type === "SYSTEM_ERROR",
      )
    )
      return "failed";
    if ((warnings ?? []).length > 0) return "warnings";
    return "passed";
  }

  function buildWarningSummary(
    warnings: (string | GroundingWarningItem)[],
  ): string[] {
    const counts: Record<string, number> = {};
    for (const w of warnings) {
      if (typeof w === "object" && (w as GroundingWarningItem).type) {
        const t = (w as GroundingWarningItem).type!;
        counts[t] = (counts[t] ?? 0) + 1;
      }
    }
    const lines: string[] = [];
    if (counts["UNVERIFIABLE_CLAIM"])
      lines.push(
        `${counts["UNVERIFIABLE_CLAIM"]} unsupported claim${counts["UNVERIFIABLE_CLAIM"] > 1 ? "s" : ""} detected.`,
      );
    if (counts["RBI_COMPLIANCE"])
      lines.push(
        `${counts["RBI_COMPLIANCE"]} RBI compliance issue${counts["RBI_COMPLIANCE"] > 1 ? "s" : ""} found.`,
      );
    if (counts["AUTHORITY_EXCEEDED"])
      lines.push(
        `${counts["AUTHORITY_EXCEEDED"]} authority violation${counts["AUTHORITY_EXCEEDED"] > 1 ? "s" : ""} detected.`,
      );
    return lines;
  }
  ```

- [ ] **Step 2: Replace the old grounding section (lines 447–468) with the new always-rendered section**

  Remove the entire existing block:
  ```tsx
  {/* Grounding info */}
  {apiDetail?.grounding_score !== undefined && (
    <section className="rounded-md p-3 border border-slate-200 bg-slate-50/80 text-xs text-slate-700">
      <div className="font-semibold text-slate-800 mb-1">
        Source check
      </div>
      <div>
        Match score:{" "}
        <span className="font-semibold text-ub-blue">
          {Math.round(apiDetail.grounding_score * 100)}%
        </span>
      </div>
      {apiDetail.grounding_warnings &&
        apiDetail.grounding_warnings.length > 0 && (
          <ul className="mt-1.5 space-y-1">
            {apiDetail.grounding_warnings.map((w, i) => (
              <GroundingWarningRow key={i} w={w} />
            ))}
          </ul>
        )}
    </section>
  )}
  ```

  Replace with:
  ```tsx
  {/* Grounding info — always rendered when apiDetail exists */}
  {apiDetail && (() => {
    const gStatus = deriveGroundingStatus(
      apiDetail.grounding_score,
      apiDetail.grounding_warnings,
    );
    const nonSystemWarnings = (apiDetail.grounding_warnings ?? []).filter(
      (w) => !(typeof w === "object" && (w as GroundingWarningItem).type === "SYSTEM_ERROR"),
    );
    const warningSummary = buildWarningSummary(nonSystemWarnings);

    const badgeClass =
      gStatus === "passed"
        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
        : gStatus === "warnings"
          ? "bg-amber-50 text-amber-700 border-amber-200"
          : gStatus === "failed"
            ? "bg-red-50 text-red-700 border-red-200"
            : "bg-slate-100 text-slate-500 border-slate-200";

    const badgeLabel =
      gStatus === "passed"
        ? "✅ Passed"
        : gStatus === "warnings"
          ? "⚠ Warnings Found"
          : gStatus === "failed"
            ? "✗ Failed"
            : "⊘ Not Executed";

    return (
      <section className="rounded-md p-3 border border-slate-200 bg-slate-50/80 text-xs text-slate-700">
        {/* Header row */}
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold text-slate-800">Grounding Check</div>
          <div className="flex items-center gap-2">
            {gStatus === "passed" && (
              <span className="text-slate-500">100%</span>
            )}
            {gStatus === "warnings" && apiDetail.grounding_score != null && (
              <span className="text-slate-500">
                {Math.round(apiDetail.grounding_score * 100)}%
              </span>
            )}
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${badgeClass}`}
            >
              {badgeLabel}
            </span>
          </div>
        </div>

        {/* Passed */}
        {gStatus === "passed" && (
          <div className="space-y-1.5">
            <div className="text-slate-500 font-medium">Why it passed</div>
            <ul className="space-y-0.5 text-slate-600">
              <li>• No unsupported or unverifiable claims were detected.</li>
              <li>• The response is consistent with the complaint context.</li>
              <li>• No RBI compliance issues were found.</li>
              <li>• The AI did not exceed its authority or make unsupported commitments.</li>
            </ul>
          </div>
        )}

        {/* Warnings Found */}
        {gStatus === "warnings" && (
          <div className="space-y-2">
            <div>
              <div className="text-slate-500 font-medium mb-1">
                Why it needs verification
              </div>
              <ul className="space-y-0.5 text-slate-600">
                {warningSummary.map((line, i) => (
                  <li key={i}>• {line}</li>
                ))}
              </ul>
            </div>
            {nonSystemWarnings.length > 0 && (
              <div>
                <div className="text-slate-500 font-medium mb-1">Details</div>
                <ul className="space-y-1">
                  {nonSystemWarnings.map((w, i) => (
                    <GroundingWarningRow key={i} w={w} />
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Skipped */}
        {gStatus === "skipped" && (
          <div className="space-y-1.5">
            <div className="text-slate-500 font-medium">Why it was skipped</div>
            <p className="text-slate-600">
              {apiDetail.is_duplicate === true
                ? "Duplicate complaint detected. The pipeline ended before the grounding stage. No AI response was generated for validation."
                : "The complaint was escalated or terminated before a draft response was generated."}
            </p>
          </div>
        )}

        {/* Failed */}
        {gStatus === "failed" && (
          <div className="space-y-1.5">
            <div className="text-slate-500 font-medium">Why it failed</div>
            <ul className="space-y-0.5 text-slate-600">
              <li>• The grounding service encountered an internal error.</li>
              <li>• The AI response could not be validated.</li>
              <li>• The complaint has been routed for human review.</li>
            </ul>
          </div>
        )}
      </section>
    );
  })()}
  ```

- [ ] **Step 3: Run the TypeScript build to verify no type errors**

  ```bash
  cd frontend
  npm run build
  ```
  Expected: build completes with exit code 0. Fix any type errors before proceeding.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/complaints/detail/ComplaintDetailPanel.tsx
  git commit -m "feat: redesign grounding section with four explicit states"
  ```

---

## Self-Review

**Spec coverage:**
- ✅ `graph.py` sentinel `0.5 → 0.0` — Task 1
- ✅ `_normalize_grounding_state` helper — Task 2 Step 1
- ✅ `or 0.8` fallback replaced — Task 2 Step 2
- ✅ Agent 9 exception handler in partial runner — Task 2 Step 3
- ✅ UI always renders grounding section — Task 3
- ✅ `deriveGroundingStatus` — Task 3 Step 1
- ✅ `buildWarningSummary` — Task 3 Step 1
- ✅ All four states rendered — Task 3 Step 2
- ✅ `is_duplicate` branch for Skipped — Task 3 Step 2
- ✅ SYSTEM_ERROR warnings excluded from Warnings view — Task 3 Step 2
- ✅ `GroundingWarningRow` untouched — no task needed

**No placeholders:** All steps contain actual code.

**Type consistency:** `GroundingWarningItem` is already imported at line 17 of the file. `deriveGroundingStatus` and `buildWarningSummary` both use the same `(string | GroundingWarningItem)[]` type matching the existing `grounding_warnings` type in `ApiComplaint`.
