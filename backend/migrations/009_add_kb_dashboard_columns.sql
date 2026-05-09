-- Migration 009: Add KB Admin Dashboard Columns
-- Run this in the Supabase SQL Editor (or via psql).
--
-- Adds two optional columns to knowledge_base:
--   issue_type   — short label for the issue (e.g. "Transaction Failed")
--   usage_count  — how many times this entry was retrieved by the RAG agent
--
-- The dashboard works without these columns (graceful fallback),
-- but adding them enables richer analytics and search.

ALTER TABLE knowledge_base
    ADD COLUMN IF NOT EXISTS issue_type   TEXT,
    ADD COLUMN IF NOT EXISTS usage_count  INTEGER NOT NULL DEFAULT 0;

-- Speed up admin list queries
CREATE INDEX IF NOT EXISTS idx_kb_issue_type
    ON knowledge_base (issue_type)
    WHERE issue_type IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_kb_usage_count
    ON knowledge_base (usage_count DESC);

CREATE INDEX IF NOT EXISTS idx_kb_tier_category
    ON knowledge_base (tier_level, category);

CREATE INDEX IF NOT EXISTS idx_kb_verified_tier
    ON knowledge_base (verified, tier_level);

-- Optional: increment usage_count via a lightweight RPC callable from the RAG agent.
-- Call it with: supabase.rpc("increment_kb_usage", {"entry_id": <id>}).execute()
CREATE OR REPLACE FUNCTION increment_kb_usage(entry_id BIGINT)
RETURNS VOID
LANGUAGE SQL
AS $$
    UPDATE knowledge_base
    SET usage_count = usage_count + 1
    WHERE id = entry_id;
$$;
