-- Migration: Agent Dashboard Tables
-- Run this in Supabase SQL Editor

BEGIN;

-- 1. Create agent_queue table
CREATE TABLE IF NOT EXISTS agent_queue (
    id BIGSERIAL PRIMARY KEY,
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    tier_level INTEGER NOT NULL CHECK (tier_level BETWEEN 0 AND 5),
    status TEXT NOT NULL DEFAULT 'QUEUED' 
        CHECK (status IN ('QUEUED', 'ASSIGNED', 'IN_REVIEW', 'COMPLETED')),
    assigned_to TEXT,
    assigned_at TIMESTAMPTZ,
    priority_score FLOAT NOT NULL DEFAULT 0,
    queue_position INTEGER,
    sla_deadline TIMESTAMPTZ,
    estimated_review_time INTEGER DEFAULT 15,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_complaint_queue UNIQUE (complaint_id)
);

CREATE INDEX idx_agent_queue_tier ON agent_queue(tier_level);
CREATE INDEX idx_agent_queue_status ON agent_queue(status);
CREATE INDEX idx_agent_queue_assigned ON agent_queue(assigned_to);
CREATE INDEX idx_agent_queue_priority ON agent_queue(priority_score DESC);
CREATE INDEX idx_agent_queue_sla ON agent_queue(sla_deadline);

-- 2. Create agent_assignments table
CREATE TABLE IF NOT EXISTS agent_assignments (
    id BIGSERIAL PRIMARY KEY,
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    tier_level INTEGER NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_review_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    action_taken TEXT CHECK (action_taken IN ('ACCEPT', 'EDIT', 'REJECT', 'MANUAL_ESCALATE')),
    time_spent_seconds INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_assignments_complaint ON agent_assignments(complaint_id);
CREATE INDEX idx_agent_assignments_agent ON agent_assignments(agent_id);
CREATE INDEX idx_agent_assignments_completed ON agent_assignments(completed_at);
CREATE INDEX idx_agent_assignments_action ON agent_assignments(action_taken);

-- 3. Modify complaints table
ALTER TABLE complaints
ADD COLUMN IF NOT EXISTS assigned_agent_id TEXT,
ADD COLUMN IF NOT EXISTS review_started_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS human_review_completed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS agent_action TEXT 
    CHECK (agent_action IN ('ACCEPT', 'EDIT', 'REJECT', 'MANUAL_ESCALATE')),
ADD COLUMN IF NOT EXISTS agent_notes TEXT,
ADD COLUMN IF NOT EXISTS draft_response_text TEXT,
ADD COLUMN IF NOT EXISTS final_response_text TEXT,
ADD COLUMN IF NOT EXISTS last_confidence FLOAT;

CREATE INDEX IF NOT EXISTS idx_complaints_assigned_agent 
    ON complaints(assigned_agent_id);

-- 4. Auto-populate queue trigger
CREATE OR REPLACE FUNCTION add_to_agent_queue()
RETURNS TRIGGER AS $$
DECLARE
    priority FLOAT;
BEGIN
    IF NEW.status = 'pending_review' AND (OLD.status IS NULL OR OLD.status != 'pending_review') THEN
        priority := (
            COALESCE(NEW.severity, 3) * 10 +
            COALESCE(NEW.urgency_score, 5) * 5 +
            (CASE WHEN NEW.rbi_reportable THEN 20 ELSE 0 END)
        );
        
        INSERT INTO agent_queue (
            complaint_id, tier_level, status, 
            priority_score, sla_deadline, estimated_review_time
        ) VALUES (
            NEW.complaint_id,
            NEW.current_tier,
            'QUEUED',
            priority,
            NEW.rbi_tat_deadline,
            CASE 
                WHEN NEW.severity >= 4 THEN 10
                WHEN NEW.category = 'Fraud' THEN 20
                ELSE 15
            END
        )
        ON CONFLICT (complaint_id) DO UPDATE
        SET tier_level = NEW.current_tier,
            priority_score = priority,
            updated_at = NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_add_to_agent_queue ON complaints;
CREATE TRIGGER trigger_add_to_agent_queue
    AFTER UPDATE ON complaints
    FOR EACH ROW
    EXECUTE FUNCTION add_to_agent_queue();

COMMIT;

-- Verify
SELECT 'Migration completed successfully!' AS status;