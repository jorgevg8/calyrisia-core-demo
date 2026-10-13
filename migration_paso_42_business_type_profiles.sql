CREATE TABLE IF NOT EXISTS business_type_profiles (
    id UUID PRIMARY KEY,
    profile_key VARCHAR(80) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_type_profiles_enabled
    ON business_type_profiles (enabled);

-- The profile definitions are data, not Python logic. Add/change profiles here
-- without changing the Galaxy Core code.
