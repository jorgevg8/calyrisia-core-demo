-- Galaxy Step 46 — Approval & Human Operations Center V2
-- Idempotent migration. Existing approvals/actions tables are preserved.

ALTER TABLE approvals
    ADD COLUMN IF NOT EXISTS decision_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE approvals
    ADD COLUMN IF NOT EXISTS decision_at TIMESTAMPTZ;

ALTER TABLE approvals
    ADD COLUMN IF NOT EXISTS decision_reason TEXT;

ALTER TABLE approvals
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE approvals
    ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE approvals
    ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '24 hours');

UPDATE approvals
SET expires_at = requested_at + INTERVAL '24 hours'
WHERE expires_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_approvals_business_status_requested
    ON approvals (business_id, status, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_approvals_business_expires
    ON approvals (business_id, expires_at);

CREATE INDEX IF NOT EXISTS idx_approvals_action
    ON approvals (business_id, action_id);
