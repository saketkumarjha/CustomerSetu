-- Migration: add_agent_queue_tables
-- Run against your Supabase project via the SQL editor or supabase CLI.
-- All changes are additive (no data loss).

-- ── 1. agent_queue table ──────────────────────────────────────────────────────
-- Tracks every complaint waiting for or under human review.

CREATE TABLE IF NOT EXISTS agent_queue (
    id                      BIGSERIAL PRIMARY KEY,
    complaint_id            TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    tier_level              INTEGER     NOT NULL,
    assigned_to             TEXT,                               -- agent_id, NULL if unassigned
    assigned_at             TIMESTAMPTZ,
    priority_score          FLOAT       NOT NULL DEFAULT 0.0,   -- higher = more urgent
    queue_position          INTEGER,
    status                  VARCHAR(20) NOT NULL DEFAULT 'QUEUED',  -- QUEUED | ASSIGNED | IN_REVIEW | COMPLETED
    sla_deadline            TIMESTAMPTZ,
    estimated_review_time   INTEGER,                            -- minutes
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_aq_status CHECK (status IN ('QUEUED', 'ASSIGNED', 'IN_REVIEW', 'COMPLETED'))
);

CREATE INDEX IF NOT EXISTS idx_agent_queue_complaint
    ON agent_queue (complaint_id);

CREATE INDEX IF NOT EXISTS idx_agent_queue_tier_status
    ON agent_queue (tier_level, status);

CREATE INDEX IF NOT EXISTS idx_agent_queue_priority
    ON agent_queue (tier_level, status, priority_score DESC)
    WHERE status IN ('QUEUED', 'ASSIGNED');

CREATE INDEX IF NOT EXISTS idx_agent_queue_assigned
    ON agent_queue (assigned_to)
    WHERE assigned_to IS NOT NULL;


-- ── 2. agent_assignments table ────────────────────────────────────────────────
-- Full audit trail of every human agent review.

CREATE TABLE IF NOT EXISTS agent_assignments (
    id                  BIGSERIAL PRIMARY KEY,
    complaint_id        TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    agent_id            TEXT        NOT NULL,
    tier_level          INTEGER     NOT NULL,
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_review_at   TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    action_taken        VARCHAR(20),                            -- ACCEPT | EDIT | REJECT | ESCALATE
    time_spent_seconds  INTEGER,
    notes               TEXT,
    CONSTRAINT chk_aa_action CHECK (
        action_taken IS NULL OR
        action_taken IN ('ACCEPT', 'EDIT', 'REJECT', 'ESCALATE')
    )
);

CREATE INDEX IF NOT EXISTS idx_agent_assignments_complaint
    ON agent_assignments (complaint_id);

CREATE INDEX IF NOT EXISTS idx_agent_assignments_agent
    ON agent_assignments (agent_id);

CREATE INDEX IF NOT EXISTS idx_agent_assignments_tier
    ON agent_assignments (tier_level, assigned_at DESC);


-- ── 3. agent_feedback table ───────────────────────────────────────────────────
-- Stores agent actions and their quality signals for model improvement.

CREATE TABLE IF NOT EXISTS agent_feedback (
    id                      BIGSERIAL PRIMARY KEY,
    complaint_id            TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    agent_id                TEXT        NOT NULL,
    action_type             VARCHAR(20) NOT NULL,               -- ACCEPT | EDIT | REJECT | ESCALATE
    original_draft          TEXT,                               -- Agent 8's response
    agent_output            TEXT,                               -- edited / rejected / accepted text
    confidence_at_review    FLOAT,
    time_spent_seconds      INTEGER,
    action_timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    feedback_score          FLOAT,                              -- 1.0 accept | 0.5 edit | 0.0 reject | -0.5 escalate
    CONSTRAINT chk_af_action CHECK (action_type IN ('ACCEPT', 'EDIT', 'REJECT', 'ESCALATE'))
);

CREATE INDEX IF NOT EXISTS idx_agent_feedback_complaint
    ON agent_feedback (complaint_id);

CREATE INDEX IF NOT EXISTS idx_agent_feedback_agent
    ON agent_feedback (agent_id, action_timestamp DESC);


-- ── 4. complaint_status_history table ────────────────────────────────────────
-- Tracks every status transition for a complaint (for audit + SLA tracking).

CREATE TABLE IF NOT EXISTS complaint_status_history (
    id              BIGSERIAL PRIMARY KEY,
    complaint_id    TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    old_status      TEXT,
    new_status      TEXT        NOT NULL,
    changed_by      TEXT,                                       -- agent_id or 'SYSTEM'
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_status_history_complaint
    ON complaint_status_history (complaint_id, changed_at DESC);


-- ── 5. complaint_escalation_history table ─────────────────────────────────────
-- Tracks tier escalations, including manual ones by human agents.

CREATE TABLE IF NOT EXISTS complaint_escalation_history (
    id                  BIGSERIAL PRIMARY KEY,
    complaint_id        TEXT        NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    from_tier           INTEGER     NOT NULL,
    to_tier             INTEGER     NOT NULL,
    escalated_by        TEXT        NOT NULL,                   -- SYSTEM | HUMAN
    escalation_reason   TEXT        NOT NULL,                   -- AUTO | MANUAL | RBI | KEYWORD | etc.
    agent_reasoning     TEXT,                                   -- human-written reason (if manual)
    agent_id            TEXT,                                   -- null for system escalations
    escalated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escalation_history_complaint
    ON complaint_escalation_history (complaint_id);


-- ── 6. New columns on complaints table ───────────────────────────────────────

ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS assigned_agent_id          TEXT,
    ADD COLUMN IF NOT EXISTS review_started_at          TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS human_review_completed_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS agent_action               VARCHAR(20),  -- ACCEPT | EDIT | REJECT | MANUAL_ESCALATE
    ADD COLUMN IF NOT EXISTS agent_notes                TEXT,
    ADD COLUMN IF NOT EXISTS escalation_not_triggered_reason TEXT,
    ADD COLUMN IF NOT EXISTS queue_position             INTEGER,
    ADD COLUMN IF NOT EXISTS tier_pending_at            INTEGER;      -- tier at which pending_review was set
