CREATE TABLE IF NOT EXISTS customer_360_profiles (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    lifecycle_stage VARCHAR(50) NOT NULL DEFAULT 'lead',
    segment VARCHAR(100),
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    communication_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    consent JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary TEXT,
    value_score NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (value_score BETWEEN 0 AND 100),
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_spend NUMERIC(14,2) NOT NULL DEFAULT 0,
    conversation_count INTEGER NOT NULL DEFAULT 0,
    last_order_at TIMESTAMPTZ,
    last_conversation_at TIMESTAMPTZ,
    last_appointment_at TIMESTAMPTZ,
    last_channel VARCHAR(30),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (business_id, customer_id)
);

CREATE INDEX IF NOT EXISTS idx_customer_360_business_customer
    ON customer_360_profiles (business_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_360_business_segment
    ON customer_360_profiles (business_id, segment, lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_customer_360_updated
    ON customer_360_profiles (business_id, updated_at DESC);
