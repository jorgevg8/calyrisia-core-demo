-- =============================================================================
-- CALYRISIA — SCRIPT MAESTRO DE PRODUCCIÓN Y SEGURIDAD RLS PARA SUPABASE
-- Compatible con: Supabase PostgreSQL + PostgREST + Render (calyrisia.com)
-- Idempotente: Seguro de ejecutar múltiples veces en el SQL Editor de Supabase.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================================
-- 1. TABLAS NUCLEARES DEL SISTEMA (CORE & MULTI-TENANT)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(200),
    business_type VARCHAR(80) NOT NULL DEFAULT 'sales_small',
    description TEXT,
    phone VARCHAR(80),
    email VARCHAR(254),
    website VARCHAR(255),
    timezone VARCHAR(80) NOT NULL DEFAULT 'America/Caracas',
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    plan_code VARCHAR(30) NOT NULL DEFAULT 'emprendedor',
    webchat_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS legal_name VARCHAR(200);
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS business_type VARCHAR(80) NOT NULL DEFAULT 'sales_small';
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS phone VARCHAR(80);
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS email VARCHAR(254);
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS website VARCHAR(255);
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS timezone VARCHAR(80) NOT NULL DEFAULT 'America/Caracas';
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS currency VARCHAR(10) NOT NULL DEFAULT 'USD';
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active';
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS plan_code VARCHAR(30) NOT NULL DEFAULT 'emprendedor';
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS webchat_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE public.businesses
SET plan_code = 'emprendedor'
WHERE plan_code IS NULL OR plan_code NOT IN ('emprendedor', 'smart_business', 'enterprise');

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    email VARCHAR(254) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(40) NOT NULL DEFAULT 'OWNER',
    full_name VARCHAR(200),
    phone VARCHAR(80),
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS full_name VARCHAR(200);
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS phone VARCHAR(80);
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_users_lower_email ON public.users (LOWER(email));
CREATE INDEX IF NOT EXISTS idx_users_business_id ON public.users (business_id);

CREATE TABLE IF NOT EXISTS public.business_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    industry VARCHAR(120),
    short_description TEXT,
    legal_name VARCHAR(200),
    address TEXT,
    city VARCHAR(120),
    state_province VARCHAR(120),
    country VARCHAR(120),
    postal_code VARCHAR(40),
    operating_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
    policies JSONB NOT NULL DEFAULT '{}'::jsonb,
    processes JSONB NOT NULL DEFAULT '{}'::jsonb,
    objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    autonomy_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    communication_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    social_links JSONB NOT NULL DEFAULT '{}'::jsonb,
    additional_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    profile_version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS city VARCHAR(120);
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS state_province VARCHAR(120);
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS country VARCHAR(120);
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS postal_code VARCHAR(40);
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS operating_hours JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS policies JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS processes JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS objectives JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS autonomy_config JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS communication_config JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS social_links JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS additional_settings JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS profile_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE public.business_profiles ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active';
CREATE INDEX IF NOT EXISTS idx_business_profiles_business ON public.business_profiles (business_id, status);

CREATE TABLE IF NOT EXISTS public.business_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    rule_key VARCHAR(120) NOT NULL,
    rule_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 2. CLIENTES, CONVERSACIONES, MEMORIA Y PERFILES 360
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(254),
    phone VARCHAR(80),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    source VARCHAR(80) DEFAULT 'webchat',
    channel VARCHAR(50) DEFAULT 'webchat',
    first_contact_at TIMESTAMPTZ DEFAULT now(),
    last_interaction_at TIMESTAMPTZ DEFAULT now(),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS email VARCHAR(254);
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS phone VARCHAR(80);
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS status VARCHAR(40) NOT NULL DEFAULT 'active';
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS source VARCHAR(80) DEFAULT 'webchat';
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS channel VARCHAR(50) DEFAULT 'webchat';
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS last_interaction_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_id_business_id ON public.customers (id, business_id);
CREATE INDEX IF NOT EXISTS idx_customers_business_created ON public.customers (business_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL DEFAULT 'webchat',
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    intent VARCHAR(120),
    topic VARCHAR(200),
    outcome VARCHAR(120),
    handoff_to_human BOOLEAN NOT NULL DEFAULT false,
    transfer_reason TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS intent VARCHAR(120);
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS topic VARCHAR(200);
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS outcome VARCHAR(120);
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS handoff_to_human BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS transfer_reason TEXT;
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_conversations_business_customer ON public.conversations (business_id, customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
    sender_type VARCHAR(50) NOT NULL DEFAULT 'customer',
    direction VARCHAR(30) NOT NULL DEFAULT 'inbound',
    message_type VARCHAR(40) NOT NULL DEFAULT 'text',
    content TEXT NOT NULL,
    intent VARCHAR(120),
    sentiment VARCHAR(60),
    tool_used TEXT,
    action_taken TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.conversation_messages ADD COLUMN IF NOT EXISTS intent VARCHAR(120);
ALTER TABLE public.conversation_messages ADD COLUMN IF NOT EXISTS sentiment VARCHAR(60);
ALTER TABLE public.conversation_messages ADD COLUMN IF NOT EXISTS tool_used TEXT;
ALTER TABLE public.conversation_messages ADD COLUMN IF NOT EXISTS action_taken TEXT;
ALTER TABLE public.conversation_messages ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_conv_messages_conv_created ON public.conversation_messages (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_messages_business_cust ON public.conversation_messages (business_id, customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES public.customers(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    memory_type VARCHAR(80) NOT NULL DEFAULT 'fact',
    memory_key VARCHAR(160),
    content TEXT NOT NULL,
    source VARCHAR(120) DEFAULT 'brain',
    confidence NUMERIC(5,2) DEFAULT 90.0,
    importance INTEGER DEFAULT 50,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_memory_business_customer ON public.memory (business_id, customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.customer_360_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, customer_id)
);

-- =============================================================================
-- 3. CATÁLOGO, INVENTARIO, IMÁGENES, PEDIDOS Y CITAS/RESERVAS
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    sku VARCHAR(100),
    description TEXT,
    category VARCHAR(120) DEFAULT 'General',
    brand VARCHAR(120),
    price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    cost_price NUMERIC(12,2) DEFAULT 0.00,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    is_service BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.products ADD COLUMN IF NOT EXISTS sku VARCHAR(100);
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS category VARCHAR(120) DEFAULT 'General';
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS brand VARCHAR(120);
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS cost_price NUMERIC(12,2) DEFAULT 0.00;
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active';
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS is_service BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_products_business_status ON public.products (business_id, status, name);

CREATE TABLE IF NOT EXISTS public.inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    quantity NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    minimum_quantity NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    location VARCHAR(120) DEFAULT 'tienda',
    last_counted_at TIMESTAMPTZ,
    last_count_method VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.inventory ADD COLUMN IF NOT EXISTS minimum_quantity NUMERIC(12,2) NOT NULL DEFAULT 0.00;
ALTER TABLE public.inventory ADD COLUMN IF NOT EXISTS location VARCHAR(120) DEFAULT 'tienda';
ALTER TABLE public.inventory ADD COLUMN IF NOT EXISTS last_counted_at TIMESTAMPTZ;
ALTER TABLE public.inventory ADD COLUMN IF NOT EXISTS last_count_method VARCHAR(80);
CREATE INDEX IF NOT EXISTS idx_inventory_business_product ON public.inventory (business_id, product_id);

CREATE TABLE IF NOT EXISTS public.product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(image_url) <= 2048)
);
CREATE INDEX IF NOT EXISTS idx_product_images_tenant_product ON public.product_images (business_id, product_id, position);

CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
    order_number VARCHAR(80) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    tax_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    payment_status VARCHAR(40) NOT NULL DEFAULT 'pending',
    payment_method VARCHAR(60),
    source VARCHAR(60) DEFAULT 'webchat',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_orders_business_created ON public.orders (business_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.products(id) ON DELETE SET NULL,
    quantity NUMERIC(12,2) NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    tax_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    line_total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON public.order_items (order_id, business_id);

CREATE TABLE IF NOT EXISTS public.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
    service_name VARCHAR(200),
    scheduled_at TIMESTAMPTZ,
    starts_at TIMESTAMPTZ,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    booking_type VARCHAR(20) NOT NULL CHECK (booking_type IN ('appointment', 'reservation')),
    customer_name VARCHAR(200) NOT NULL,
    customer_phone VARCHAR(80),
    party_size INTEGER NOT NULL DEFAULT 1 CHECK (party_size >= 1 AND party_size <= 200),
    starts_at TIMESTAMPTZ NOT NULL,
    service_name VARCHAR(200) NOT NULL,
    table_number VARCHAR(30),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_business_bookings_tenant_start ON public.business_bookings (business_id, booking_type, starts_at);

CREATE TABLE IF NOT EXISTS public.business_dashboard_settings (
    business_id UUID PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
    restaurant_table_count INTEGER NOT NULL DEFAULT 12 CHECK (restaurant_table_count BETWEEN 1 AND 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_ai_usage_monthly (
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    month_start DATE NOT NULL,
    response_count INTEGER NOT NULL DEFAULT 0 CHECK (response_count >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, month_start)
);

-- =============================================================================
-- 4. PAGOS DE WEBCHAT, CANALES (TELEGRAM) Y CHECKOUT COMERCIAL DE CALYRISIA
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.webchat_payment_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE RESTRICT,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    payment_method VARCHAR(50) NOT NULL DEFAULT 'manual',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    source VARCHAR(50) NOT NULL DEFAULT 'webchat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    order_id UUID REFERENCES public.orders(id) ON DELETE SET NULL,
    approval_note TEXT,
    items JSONB,
    customer_payment_details TEXT
);

ALTER TABLE public.webchat_payment_requests ADD COLUMN IF NOT EXISTS items JSONB;
ALTER TABLE public.webchat_payment_requests ADD COLUMN IF NOT EXISTS customer_payment_details TEXT;
ALTER TABLE public.webchat_payment_requests ALTER COLUMN payment_method SET DEFAULT 'manual';
ALTER TABLE public.webchat_payment_requests ALTER COLUMN source SET DEFAULT 'webchat';

CREATE INDEX IF NOT EXISTS idx_webchat_payments_business_status_created
    ON public.webchat_payment_requests (business_id, status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_webchat_payment_order_id
    ON public.webchat_payment_requests (order_id) WHERE order_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_webchat_payment_customer_tenant'
          AND conrelid = 'public.webchat_payment_requests'::regclass
    ) THEN
        ALTER TABLE public.webchat_payment_requests
            ADD CONSTRAINT fk_webchat_payment_customer_tenant
            FOREIGN KEY (customer_id, business_id)
            REFERENCES public.customers (id, business_id)
            ON DELETE RESTRICT NOT VALID;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.business_payment_instructions (
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    method_code VARCHAR(30) NOT NULL CHECK (method_code IN ('pago_movil', 'binance')),
    enabled BOOLEAN NOT NULL DEFAULT false,
    instructions TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, method_code),
    CHECK (length(instructions) <= 3000)
);

CREATE TABLE IF NOT EXISTS public.business_telegram_channels (
    business_id UUID PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
    bot_token TEXT NOT NULL,
    bot_username VARCHAR(80),
    owner_chat_id VARCHAR(80),
    enabled BOOLEAN NOT NULL DEFAULT false,
    channel_status VARCHAR(20) NOT NULL DEFAULT 'inactive',
    polling_offset BIGINT NOT NULL DEFAULT 0,
    last_error TEXT,
    last_poll_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_business_telegram_bot_token ON public.business_telegram_channels (bot_token);

CREATE TABLE IF NOT EXISTS public.telegram_customer_sessions (
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    telegram_user_id VARCHAR(80) NOT NULL,
    chat_id VARCHAR(80) NOT NULL,
    customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    telegram_username VARCHAR(255),
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, telegram_user_id)
);

CREATE TABLE IF NOT EXISTS public.telegram_update_events (
    update_id BIGINT PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.calyrisia_checkout_orders (
    checkout_ref VARCHAR(64) PRIMARY KEY,
    plan_code VARCHAR(32) NOT NULL CHECK (plan_code IN ('emprendedor', 'smart_business', 'enterprise')),
    amount NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    payment_method VARCHAR(30) NOT NULL DEFAULT 'pending',
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'awaiting_payment', 'paid', 'failed', 'cancelled')),
    paypal_subscription_id VARCHAR(128) UNIQUE,
    paypal_plan_id VARCHAR(128),
    paypal_transaction_id VARCHAR(128),
    subscription_status VARCHAR(32),
    webhook_event_id VARCHAR(128),
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(160),
    review_note TEXT,
    customer_name VARCHAR(160),
    customer_email VARCHAR(254),
    customer_phone VARCHAR(64),
    business_name VARCHAR(180),
    contact_saved_at TIMESTAMPTZ,
    transaction_reference VARCHAR(180),
    proof_note TEXT,
    proof_submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_calyrisia_checkout_status_created ON public.calyrisia_checkout_orders (status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.calyrisia_paypal_pending_sales (
    subscription_id VARCHAR(128) NOT NULL,
    transaction_id VARCHAR(128) NOT NULL,
    event_id VARCHAR(128),
    amount NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (subscription_id, transaction_id)
);

-- =============================================================================
-- 5. GOBERNANZA, ACCIONES (public.actions), APROBACIONES Y AUDITORÍA
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    subject_type VARCHAR(50) NOT NULL DEFAULT 'system',
    subject_id UUID,
    role VARCHAR(50),
    resource_type VARCHAR(80) NOT NULL,
    action_type VARCHAR(80) NOT NULL,
    effect VARCHAR(20) NOT NULL DEFAULT 'allow',
    requires_approval BOOLEAN NOT NULL DEFAULT false,
    limits JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_permissions_business_resource ON public.permissions (business_id, resource_type, action_type, enabled);

CREATE TABLE IF NOT EXISTS public.actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    requested_by_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    permission_id UUID REFERENCES public.permissions(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    tool_name VARCHAR(120),
    autonomy_level VARCHAR(50) DEFAULT 'assisted',
    risk_level VARCHAR(40) DEFAULT 'medium',
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    error_message TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_actions_business_status ON public.actions (business_id, status, requested_at DESC);

CREATE TABLE IF NOT EXISTS public.approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    action_id UUID NOT NULL REFERENCES public.actions(id) ON DELETE CASCADE,
    requested_by_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    reason TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decision_by_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    decision_at TIMESTAMPTZ,
    decision_reason TEXT,
    expires_at TIMESTAMPTZ DEFAULT (now() + INTERVAL '24 hours'),
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_approvals_business_status_requested ON public.approvals (business_id, status, requested_at DESC);

CREATE TABLE IF NOT EXISTS public.events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    event_id VARCHAR(160) NOT NULL,
    event_type VARCHAR(120) NOT NULL,
    source VARCHAR(100) DEFAULT 'system',
    priority VARCHAR(30) DEFAULT 'normal',
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    entity_type VARCHAR(100),
    entity_id UUID,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_started_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_business_event_id ON public.events (business_id, event_id);

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    event_id UUID,
    action_id UUID,
    actor_type VARCHAR(60) NOT NULL DEFAULT 'SYSTEM',
    actor_user_id UUID,
    action_type VARCHAR(120) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(160),
    status VARCHAR(50) DEFAULT 'success',
    tool_name VARCHAR(120),
    reason TEXT,
    before_data JSONB,
    after_data JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS event_id UUID;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS action_id UUID;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS actor_user_id UUID;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS resource_id VARCHAR(160);
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'success';
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS tool_name VARCHAR(120);
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS reason TEXT;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS before_data JSONB;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS after_data JSONB;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_audit_logs_business_created ON public.audit_logs (business_id, created_at DESC);

-- =============================================================================
-- 6. INTELIGENCIA ESTRATÉGICA, FLUJOS DE TRABAJO Y AUTONOMÍA
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.business_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    insight_type VARCHAR(100) NOT NULL,
    category VARCHAR(30) NOT NULL DEFAULT 'problem',
    severity VARCHAR(20) NOT NULL DEFAULT 'normal',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    entity_type VARCHAR(100),
    entity_id UUID,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    confidence NUMERIC(5,2),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    source VARCHAR(120),
    fingerprint VARCHAR(255) NOT NULL,
    source_event_id UUID,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    insight_id UUID NOT NULL REFERENCES public.business_insights(id) ON DELETE CASCADE,
    recommendation_type VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    rationale TEXT NOT NULL,
    action_type VARCHAR(120) NOT NULL,
    requires_approval BOOLEAN NOT NULL DEFAULT true,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    acted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.business_type_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_key VARCHAR(80) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_knowledge_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('knowledge', 'policy', 'faq', 'process')),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'both' CHECK (visibility IN ('customer', 'internal', 'both')),
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    source VARCHAR(250),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    trigger_event_type VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT workflow_definitions_name_uq UNIQUE (business_id, name)
);

CREATE TABLE IF NOT EXISTS public.workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES public.workflow_definitions(id) ON DELETE CASCADE,
    event_record_id UUID,
    idempotency_key VARCHAR(300) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT workflow_runs_idempotency_uq UNIQUE (workflow_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS public.workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_key VARCHAR(120) NOT NULL,
    step_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT workflow_steps_uq UNIQUE (run_id, step_key)
);

CREATE TABLE IF NOT EXISTS public.agent_blueprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    agent_name VARCHAR(150) NOT NULL,
    core_objective TEXT,
    capabilities JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomy_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    action_name VARCHAR(100) NOT NULL,
    policy_mode VARCHAR(50) NOT NULL,
    value_limit NUMERIC(12, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    name VARCHAR(150) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    target_value NUMERIC(12, 2) NOT NULL,
    current_value NUMERIC(12, 2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.event_bus_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomous_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    risk_level VARCHAR(50) DEFAULT 'medium',
    requires_approval BOOLEAN DEFAULT false,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomous_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    steps JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    task_id UUID,
    actor VARCHAR(100),
    status VARCHAR(50) DEFAULT 'running',
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.runtime_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    execution_id UUID,
    action_name VARCHAR(150),
    reason TEXT,
    impact_level VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    decided_by VARCHAR(100),
    evidence JSONB DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomous_recovery_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    task_id UUID,
    failure_reason TEXT,
    recovery_strategy VARCHAR(120),
    attempt_count INTEGER DEFAULT 1,
    max_attempts INTEGER DEFAULT 3,
    status VARCHAR(50) DEFAULT 'recovering',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomous_cost_optimizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    task_id UUID,
    task_value NUMERIC(12,2),
    estimated_cost NUMERIC(12,4),
    roi_status VARCHAR(50),
    decision VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomous_governance_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    agent_name VARCHAR(120),
    action_intent VARCHAR(150),
    risk_score NUMERIC(5,2),
    policy_evaluation VARCHAR(80),
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.autonomous_learning_loops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    action_taken VARCHAR(150),
    reasoning TEXT,
    outcome VARCHAR(100),
    learning_signal TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    anomaly_type VARCHAR(100),
    description TEXT,
    severity VARCHAR(50),
    detected_value NUMERIC(12,2),
    expected_baseline NUMERIC(12,2),
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_kpi_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    metric_name VARCHAR(120),
    current_value NUMERIC(14,2),
    previous_value NUMERIC(14,2),
    trend_percentage NUMERIC(8,2),
    trend_direction VARCHAR(30),
    insight TEXT,
    recommendation TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    title VARCHAR(200),
    description TEXT,
    opportunity_type VARCHAR(100),
    potential_value NUMERIC(14,2) DEFAULT 0.00,
    priority_score NUMERIC(8,2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'detected',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.business_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    provider VARCHAR(100) NOT NULL,
    credentials JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.customer_health_status (
    customer_id UUID NOT NULL,
    business_id UUID NOT NULL,
    sentiment_score NUMERIC(5,2),
    churn_risk VARCHAR(50),
    risk_reason TEXT,
    last_analyzed_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (business_id, customer_id)
);

CREATE TABLE IF NOT EXISTS public.external_webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    target_url TEXT,
    event_name VARCHAR(120),
    payload JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'delivered',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.idempotency_records (
    idempotency_key VARCHAR(255) NOT NULL,
    business_id UUID NOT NULL,
    action_name VARCHAR(120),
    status VARCHAR(50),
    response_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (business_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS public.llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    model_name VARCHAR(100),
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_cost NUMERIC(12,6) DEFAULT 0,
    feature_used VARCHAR(120),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.long_running_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    task_id UUID,
    execution_id UUID,
    job_name VARCHAR(150),
    status VARCHAR(50) DEFAULT 'running',
    current_checkpoint INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 1,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    state_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_delegations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    task_description TEXT,
    assigned_agent VARCHAR(120),
    payload JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'delegated',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.omnichannel_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    customer_id UUID,
    conversation_id UUID,
    channel VARCHAR(60),
    direction VARCHAR(30),
    message_content TEXT,
    status VARCHAR(50) DEFAULT 'delivered',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.proactive_engagements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    customer_id UUID,
    trigger_event VARCHAR(120),
    status VARCHAR(50) DEFAULT 'sent',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.vision_evidences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    image_url TEXT,
    operation_type VARCHAR(100),
    detected_data JSONB DEFAULT '{}'::jsonb,
    confidence NUMERIC(5,2),
    requires_human BOOLEAN DEFAULT false,
    status VARCHAR(50) DEFAULT 'processed',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.calyrisia_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rating INTEGER NOT NULL,
    experience VARCHAR(50),
    liked TEXT,
    improvements TEXT,
    author_name VARCHAR(150),
    author_email VARCHAR(150),
    business_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 7. SOLUCIÓN DEFINITIVA DE SEGURIDAD SUPABASE: RLS + GRANTS EXPLÍCITOS (OCT 30)
-- Cumple con el cambio oficial de Supabase del 30 de Octubre:
-- 1. Activa RLS en `public.actions` y en TODAS las tablas del esquema `public`.
-- 2. Revoca acceso público no autorizado (`anon` / `authenticated`) en PostgREST.
-- 3. Otorga GRANT explícito (`SELECT, INSERT, UPDATE, DELETE`) a `postgres` y
--    `service_role` tanto en las tablas actuales como en tablas futuras.
-- =============================================================================

GRANT USAGE ON SCHEMA public TO postgres, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO postgres, service_role;

DO $$
DECLARE
    tbl RECORD;
BEGIN
    FOR tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        -- 1. Activar Row Level Security en cada tabla pública (incluyendo public.actions)
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl.tablename);

        -- 2. Revocar permisos directos de la API pública PostgREST (anon / authenticated)
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated;', tbl.tablename);

        -- 3. Otorgar GRANT explícito requerido por Supabase (cambio del 30 de Octubre)
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO postgres, service_role;', tbl.tablename);

        -- 4. Crear política explícita para service_role por buenas prácticas de Supabase
        EXECUTE format('DROP POLICY IF EXISTS "service_role_full_access" ON public.%I;', tbl.tablename);
        EXECUTE format(
            'CREATE POLICY "service_role_full_access" ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true);',
            tbl.tablename
        );
    END LOOP;
END $$;