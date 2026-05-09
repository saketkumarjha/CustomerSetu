-- Migration: 010_enhance_kb_enrichment_queue
-- Adds quality signals, tier info, and admin tracking columns to kb_enrichment_queue.
-- Run via Supabase SQL editor. All changes are additive (no data loss).

-- ── 1. Extend kb_enrichment_queue ─────────────────────────────────────────────

ALTER TABLE kb_enrichment_queue
    ADD COLUMN IF NOT EXISTS tier_level                 INTEGER     DEFAULT 0,
    ADD COLUMN IF NOT EXISTS tier_scope                 TEXT,
    ADD COLUMN IF NOT EXISTS category                   TEXT,
    ADD COLUMN IF NOT EXISTS issue_type                 TEXT,
    ADD COLUMN IF NOT EXISTS confidence_score           FLOAT       DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS recommended_quality_score  FLOAT       DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS quality_signals_json       JSONB,
    ADD COLUMN IF NOT EXISTS agent_action               TEXT,       -- ACCEPT | EDIT | AUTO | null
    ADD COLUMN IF NOT EXISTS customer_feedback_score    FLOAT,      -- 1–5 CSAT rating (nullable)
    ADD COLUMN IF NOT EXISTS resolution_type            TEXT,       -- AUTO_RESPONSE | AGENT_ACCEPTED | AGENT_EDITED
    ADD COLUMN IF NOT EXISTS rejection_reason           TEXT,
    ADD COLUMN IF NOT EXISTS processed_by_admin_id      TEXT;

-- ── 2. Indexes for admin review queries ───────────────────────────────────────

-- Sort pending entries by quality desc (admin review queue)
CREATE INDEX IF NOT EXISTS idx_kb_queue_pending_quality
    ON kb_enrichment_queue (recommended_quality_score DESC)
    WHERE processed = false;

-- Look up by complaint_id to update quality when CSAT arrives
CREATE INDEX IF NOT EXISTS idx_kb_queue_complaint_pending
    ON kb_enrichment_queue (complaint_id)
    WHERE processed = false;

-- Filter by tier for bulk operations
CREATE INDEX IF NOT EXISTS idx_kb_queue_tier_pending
    ON kb_enrichment_queue (tier_level)
    WHERE processed = false;

-- Processed entries for audit/cleanup
CREATE INDEX IF NOT EXISTS idx_kb_queue_processed_at
    ON kb_enrichment_queue (processed_at DESC)
    WHERE processed = true;

-- ── 3. Ensure processed_at column exists (may be missing on older deployments) ─

ALTER TABLE kb_enrichment_queue
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;

-- ── 4. knowledge_base source column ──────────────────────────────────────────
-- Ensure the source_complaint_id column exists for traceability.

ALTER TABLE knowledge_base
    ADD COLUMN IF NOT EXISTS source_complaint_id TEXT;
