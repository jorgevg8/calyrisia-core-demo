-- ============================================================
-- GALAXY AUTOMATIONS / GALAXY BUSINESS AUTOPILOT
-- PASO 19 — BUSINESS BRAIN + RECOMMENDATION ENGINE
-- ============================================================
-- Ejecutar una sola vez en galaxy_db.

CREATE TABLE IF NOT EXISTS business_insights (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    insight_type VARCHAR(100) NOT NULL,
    category VARCHAR(30) NOT NULL DEFAULT 'problem'
        CHECK (category IN ('problem', 'opportunity', 'info')),
    severity VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (severity IN ('critical', 'high', 'normal', 'low')),
    priority VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    entity_type VARCHAR(100),
    entity_id UUID,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
    confidence NUMERIC(5,2)
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 100)),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    source VARCHAR(120),
    fingerprint VARCHAR(255) NOT NULL,
    source_event_id UUID REFERENCES events(id) ON DELETE SET NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_insights_business_status
    ON business_insights (business_id, status, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_business_insights_business_priority
    ON business_insights (business_id, priority, detected_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_business_insights_open_fingerprint
    ON business_insights (business_id, fingerprint)
    WHERE status IN ('open', 'acknowledged');

CREATE TABLE IF NOT EXISTS recommendations (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    insight_id UUID NOT NULL REFERENCES business_insights(id) ON DELETE CASCADE,
    recommendation_type VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    rationale TEXT NOT NULL,
    action_type VARCHAR(120) NOT NULL,
    requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected', 'executed', 'dismissed', 'expired')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    acted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_recommendations_insight_type
    ON recommendations (insight_id, recommendation_type);

CREATE INDEX IF NOT EXISTS idx_recommendations_business_status
    ON recommendations (business_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_business_priority
    ON recommendations (business_id, priority, created_at DESC);
