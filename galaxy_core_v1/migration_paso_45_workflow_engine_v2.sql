CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    trigger_event_type VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT workflow_definitions_name_uq UNIQUE (business_id, name)
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    event_record_id UUID REFERENCES events(id) ON DELETE SET NULL,
    idempotency_key VARCHAR(300) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT workflow_runs_idempotency_uq UNIQUE (workflow_id, idempotency_key),
    CONSTRAINT workflow_runs_status_ck CHECK (status IN ('running', 'waiting_approval', 'completed', 'failed', 'skipped'))
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_key VARCHAR(120) NOT NULL,
    step_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT workflow_steps_uq UNIQUE (run_id, step_key),
    CONSTRAINT workflow_steps_status_ck CHECK (status IN ('running', 'completed', 'waiting_approval', 'failed', 'skipped')),
    CONSTRAINT workflow_steps_type_ck CHECK (step_type IN ('condition', 'action'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_definitions_business_trigger
    ON workflow_definitions (business_id, trigger_event_type, enabled);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_business_status
    ON workflow_runs (business_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_event
    ON workflow_runs (business_id, event_record_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_run
    ON workflow_steps (run_id, step_order);
