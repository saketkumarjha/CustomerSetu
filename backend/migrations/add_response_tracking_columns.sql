-- Migration: add_response_tracking_columns
-- Run against your Supabase project via the SQL editor or supabase CLI.
-- All changes are additive (no data loss).

-- ── 1. New columns on complaints table ───────────────────────────────────────

ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS final_response_text    TEXT,
    ADD COLUMN IF NOT EXISTS response_sent_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS response_channel       VARCHAR(20),   -- email | sms | web | whatsapp
    ADD COLUMN IF NOT EXISTS tier_resolved_at       INTEGER,       -- which tier resolved it
    ADD COLUMN IF NOT EXISTS auto_response_accepted BOOLEAN;       -- set after 24 h enrichment check


-- ── 2. notification_log table ─────────────────────────────────────────────────
-- Tracks every send attempt per complaint.

CREATE TABLE IF NOT EXISTS notification_log (
    id              BIGSERIAL PRIMARY KEY,
    complaint_id    TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    channel         VARCHAR(20) NOT NULL,                          -- email | sms | web | whatsapp
    status          VARCHAR(20) NOT NULL DEFAULT 'sent',           -- sent | delivered | failed
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ,
    opened_at       TIMESTAMPTZ,                                   -- email open tracking
    failure_reason  TEXT,
    tier_level      INTEGER,
    confidence      FLOAT
);

CREATE INDEX IF NOT EXISTS idx_notification_log_complaint
    ON notification_log (complaint_id);


-- ── 3. kb_enrichment_queue table ─────────────────────────────────────────────
-- Tracks pending knowledge-base enrichment jobs (24 h after auto-response).

CREATE TABLE IF NOT EXISTS kb_enrichment_queue (
    id              BIGSERIAL PRIMARY KEY,
    complaint_id    TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    resolution_text TEXT        NOT NULL,
    scheduled_for   TIMESTAMPTZ NOT NULL,
    processed       BOOLEAN     NOT NULL DEFAULT FALSE,
    processed_at    TIMESTAMPTZ,
    added_to_kb     BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_kb_enrichment_queue_complaint
    ON kb_enrichment_queue (complaint_id);

CREATE INDEX IF NOT EXISTS idx_kb_enrichment_queue_scheduled
    ON kb_enrichment_queue (scheduled_for) WHERE processed = FALSE;
