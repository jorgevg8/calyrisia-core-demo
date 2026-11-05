CREATE TABLE IF NOT EXISTS business_knowledge_items (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('knowledge','policy','faq','process')),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'both' CHECK (visibility IN ('customer','internal','both')),
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    source VARCHAR(250),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_knowledge_items_business_status
    ON business_knowledge_items (business_id, status, priority DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_business_knowledge_items_business_type
    ON business_knowledge_items (business_id, item_type, status);
