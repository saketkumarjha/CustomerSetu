-- Baseline columns for GET /complaints/{id}/escalation-status and submit flow.
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS current_tier INTEGER NOT NULL DEFAULT 1;

ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS initial_tier INTEGER NOT NULL DEFAULT 0;

-- From add_escalation_tracking_columns.sql (if that migration was skipped)
ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS escalation_count         INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS escalation_path          JSONB        NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS max_tier_reached         INTEGER      DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_escalating            BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS escalation_loop_detected BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_escalation_at       TIMESTAMPTZ;
