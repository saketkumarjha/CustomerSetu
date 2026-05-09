-- Migration: add_escalation_tracking_columns
-- Run via Supabase SQL editor or supabase CLI.
-- All changes are additive (no data loss).

-- ── 1. New columns on complaints table ────────────────────────────────────────

ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS escalation_count         INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS escalation_path          JSONB        NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS max_tier_reached         INTEGER      DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_escalating            BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS escalation_loop_detected BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_escalation_at       TIMESTAMPTZ;

-- ── 2. Extend complaint_escalation_history ────────────────────────────────────

ALTER TABLE complaint_escalation_history
    ADD COLUMN IF NOT EXISTS agent_outputs_snapshot        JSONB,
    ADD COLUMN IF NOT EXISTS confidence_before             FLOAT,
    ADD COLUMN IF NOT EXISTS kb_coverage_before            FLOAT,
    ADD COLUMN IF NOT EXISTS tier_response_text            TEXT,
    ADD COLUMN IF NOT EXISTS tier_knowledge_used           JSONB,
    ADD COLUMN IF NOT EXISTS escalation_decision_reasoning TEXT,
    ADD COLUMN IF NOT EXISTS signals_detected              JSONB,
    ADD COLUMN IF NOT EXISTS status                        VARCHAR(20) NOT NULL DEFAULT 'completed';

-- ── 3. Indexes ─────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_escalation_complaint
    ON complaint_escalation_history (complaint_id, escalated_at DESC);

CREATE INDEX IF NOT EXISTS idx_complaints_is_escalating
    ON complaints (is_escalating) WHERE is_escalating = TRUE;

CREATE INDEX IF NOT EXISTS idx_complaints_escalation_count
    ON complaints (escalation_count) WHERE escalation_count > 0;
