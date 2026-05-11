-- Migration 012: Add missing pipeline analysis columns to complaints table
-- These columns are written by _save_pipeline_outputs() in pipeline.py but were
-- never created, causing the entire UPDATE to fail silently and leaving all
-- analysis fields null after every pipeline run.
-- Safe to run multiple times (IF NOT EXISTS / DO NOTHING).

ALTER TABLE complaints
    -- Tier-aware analysis fields (written by resolution/routing nodes)
    ADD COLUMN IF NOT EXISTS tier_scope               TEXT,
    ADD COLUMN IF NOT EXISTS tier_kb_coverage_score   FLOAT,
    ADD COLUMN IF NOT EXISTS missing_info_indicators  JSONB        NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS resolution_type          TEXT,

    -- Per-agent output fields used by agent_context_service
    ADD COLUMN IF NOT EXISTS category_confidence      FLOAT,
    ADD COLUMN IF NOT EXISTS escalation_flag          BOOLEAN,
    ADD COLUMN IF NOT EXISTS severity_breakdown       JSONB,
    ADD COLUMN IF NOT EXISTS context_documents        JSONB        NOT NULL DEFAULT '[]';
