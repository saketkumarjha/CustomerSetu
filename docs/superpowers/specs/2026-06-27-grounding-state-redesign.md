# Grounding State Redesign

**Date:** 2026-06-27
**Goal:** Make every grounding execution state — Passed, Warnings Found, Skipped, Failed — explicit, reliable, and user-friendly using only the existing `grounding_score` and `grounding_warnings` fields. No schema changes.

---

## State Contract

The two fields together encode exactly four states. All backend paths and all UI cases derive from this table and nothing else.

| State | `grounding_score` | `grounding_warnings` | Meaning |
|---|---|---|---|
| **Passed** | `> 0.0` (commonly `1.0`) | `[]` | Executed, no issues found |
| **Warnings Found** | `> 0.0` | `[{...}, ...]` | Executed, one or more issues found |
| **Skipped** | `null` | `[]` | Pipeline never reached Node 6 |
| **Failed** | `0.0` | `[{"type":"SYSTEM_ERROR",...}]` | Node 6 ran but threw an exception |

**Invariants:**
- `null` score always accompanies `[]` warnings.
- `0.0` score always accompanies at least one `SYSTEM_ERROR` warning.
- These two fields are always written together — no path writes one without the other.

---

## Backend Changes

### 1. `graph.py` — `grounding_node` exception handler

**File:** `backend/app/services/supervisor/graph.py`

**Current** (line ~629):
```python
grounding_score = 0.5
```

**Change to:**
```python
grounding_score = 0.0
```

The SYSTEM_ERROR warning structure is already correct. Only the score sentinel is wrong.

---

### 2. `partial_pipeline_runner.py` — normalization helper

**File:** `backend/app/services/partial_pipeline_runner.py`

Add this function near the top of the file (after imports):

```python
def _normalize_grounding_state(
    score: float | None,
    warnings: list,
) -> tuple[float | None, list]:
    """
    Repair inconsistent grounding state before carrying it forward into an
    escalation re-run. Enforces the state contract:
      None  + []            → Skipped
      > 0.0 + []            → Passed
      > 0.0 + [...]         → Warnings Found
      0.0   + [SYSTEM_ERROR]→ Failed
    """
    warnings = warnings or []

    if score is None:
        # No score means grounding was never executed.
        # Discard any orphaned warnings — they cannot be trusted without a score.
        return None, []

    if score == 1.0:
        # Perfect score must have no warnings.
        # Force-clear any stale warnings from legacy records.
        return 1.0, []

    if score == 0.0:
        has_system_error = any(
            isinstance(w, dict) and w.get("type") == "SYSTEM_ERROR"
            for w in warnings
        )
        if not has_system_error:
            # score=0.0 means a failed run, but the SYSTEM_ERROR sentinel is
            # missing (legacy record or partial write). Insert a synthetic one
            # so the UI correctly shows Failed rather than Skipped.
            warnings = [{
                "type": "SYSTEM_ERROR",
                "claim": "Grounding state repaired",
                "issue": "Grounding failed but no SYSTEM_ERROR warning was present.",
                "suggestion": "Review the draft manually.",
            }]
        return 0.0, warnings

    # score > 0.0 and < 1.0 — normal execution path.
    return score, warnings
```

**Current** (lines ~96–97):
```python
grounding_score: float = original_state.get("grounding_score", 0.8) or 0.8
grounding_warnings: list = original_state.get("grounding_warnings", []) or []
```

**Change to:**
```python
grounding_score, grounding_warnings = _normalize_grounding_state(
    original_state.get("grounding_score"),
    original_state.get("grounding_warnings"),
)
```

**Current** (lines ~114–115 — exception handler when Agent 9 re-runs and throws):
```python
except Exception as e:
    errors.append(f"Agent 9 (Grounding) failed at Tier {new_tier_level}: {e}")
```

**Change to:**
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

---

## UI Changes

### Files affected
- `frontend/src/components/complaints/detail/ComplaintDetailPanel.tsx`

### Status derivation

Add an inline helper `deriveGroundingStatus`:

```typescript
type GroundingStatus = "skipped" | "passed" | "warnings" | "failed";

function deriveGroundingStatus(
  score: number | null | undefined,
  warnings: (string | GroundingWarningItem)[] | undefined,
): GroundingStatus {
  if (score === null || score === undefined) return "skipped";
  if (score === 0.0 && (warnings ?? []).some(
    (w) => typeof w === "object" && w.type === "SYSTEM_ERROR"
  )) return "failed";
  if ((warnings ?? []).length > 0) return "warnings";
  return "passed";
}
```

### Warning summary computation (for Warnings Found state)

Derive human-readable summary bullets from the warnings array before rendering:

```typescript
function buildWarningSummary(warnings: (string | GroundingWarningItem)[]): string[] {
  const counts: Record<string, number> = {};
  for (const w of warnings) {
    if (typeof w === "object" && w.type) {
      counts[w.type] = (counts[w.type] ?? 0) + 1;
    }
  }
  const lines: string[] = [];
  if (counts["UNVERIFIABLE_CLAIM"])
    lines.push(`${counts["UNVERIFIABLE_CLAIM"]} unsupported claim${counts["UNVERIFIABLE_CLAIM"] > 1 ? "s" : ""} detected.`);
  if (counts["RBI_COMPLIANCE"])
    lines.push(`${counts["RBI_COMPLIANCE"]} RBI compliance issue${counts["RBI_COMPLIANCE"] > 1 ? "s" : ""} found.`);
  if (counts["AUTHORITY_EXCEEDED"])
    lines.push(`${counts["AUTHORITY_EXCEEDED"]} authority violation${counts["AUTHORITY_EXCEEDED"] > 1 ? "s" : ""} detected.`);
  return lines;
}
```

### Section always renders

Remove the current guard:
```tsx
{apiDetail?.grounding_score !== undefined && (...)}
```
Replace with unconditional render when `apiDetail` exists. The section shows for every complaint.

### Per-state rendering

**Passed — Green badge**
```
Grounding Check                           ✅ Passed  100%

Why it passed
• No unsupported or unverifiable claims were detected.
• The response is consistent with the complaint context.
• No RBI compliance issues were found.
• The AI did not exceed its authority or make unsupported commitments.
```
Fixed bullet list — these are the checks the grounding agent always performs, always displayed on pass.

**Warnings Found — Yellow badge**
```
Grounding Check                      ⚠ Warnings Found  70%

Why it needs verification
• 2 unsupported claims were detected.
• 1 RBI compliance issue was found.

Details
────────────────────────────
Claim: "Refund will be credited within 24 hours."
Issue: This timeline cannot be verified.
Suggestion: Replace with "Your complaint has been forwarded for investigation."
────────────────────────────
```
Summary bullets derived from warning type counts. Each warning detail rendered by the existing `GroundingWarningRow` component (unchanged).

**Skipped — Grey badge**
```
Grounding Check                           ⊘ Not Executed
```
Skip reason derived from `apiDetail`:
- If `is_duplicate === true`: "Duplicate complaint detected. The pipeline ended before the grounding stage. No AI response was generated for validation."
- Otherwise: "The complaint was escalated or terminated before a draft response was generated."

**Failed — Red badge**
```
Grounding Check                                ✗ Failed

Why it failed
• The grounding service encountered an internal error.
• The AI response could not be validated.
• The complaint has been routed for human review.
```
Fixed bullets only. The raw SYSTEM_ERROR warning object is **not** listed — it contains error detail that is not actionable for the agent.

---

## What Does Not Change

- Database schema — no new columns.
- `pipeline.py` final write — `state.get("grounding_score")` already serializes `None` as `null` correctly.
- `grounding_agent.py` — no changes. The agent already returns the correct structure.
- `escalation_orchestrator.py` — no changes. It forwards whatever is in the pipeline result.
- `GroundingWarningRow` component — no changes to the row renderer itself.
- `ComplaintDetailModal.tsx` — the debug JSON dump of raw warnings is left as-is (it's a developer panel, not agent-facing).

---

## Skipped Cases (for reference)

Grounding is skipped whenever the pipeline ends before Node 6. Known paths:

1. **Duplicate detection (Node 2)** — pipeline exits early via `END`. The DB row was inserted with `grounding_score: null, grounding_warnings: []` and is never updated by the pipeline final-write.
2. **Duplicate complaint submitted via channel route** — same as above; the partial insert in `channels.py` already writes `grounding_warnings: []` and `grounding_score` is never set.
3. **Email / WhatsApp insert before pipeline** — initial inserts in `email_service.py` and `whatsapp_service.py` set `grounding_warnings: []`; `grounding_score` stays null unless the pipeline runs to Node 6.

No code changes needed for these paths — the `null`/`[]` initial state is already correct.
