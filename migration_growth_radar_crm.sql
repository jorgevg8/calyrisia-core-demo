-- CALYRISIA CRM comercial + Radar operativo
-- Ejecuta una vez en Supabase SQL Editor si deseas aplicar el esquema manualmente.
-- El backend también crea estas tablas automáticamente al iniciar.

CREATE TABLE IF NOT EXISTS public.calyrisia_sales_leads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id uuid,
    customer_name varchar(200) NOT NULL,
    customer_phone varchar(80),
    customer_email varchar(254),
    source varchar(40) NOT NULL DEFAULT 'manual',
    interest text,
    expected_value numeric(14,2) CHECK (expected_value IS NULL OR expected_value >= 0),
    currency varchar(8) NOT NULL DEFAULT 'USD',
    stage varchar(24) NOT NULL DEFAULT 'new'
        CHECK (stage IN ('new','contacted','qualified','quoted','awaiting_payment','won','lost')),
    consent_status varchar(20) NOT NULL DEFAULT 'unknown'
        CHECK (consent_status IN ('unknown','granted','denied')),
    last_contact_at timestamptz,
    next_follow_up_at timestamptz,
    notes text,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, business_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_calyrisia_sales_lead_customer
    ON public.calyrisia_sales_leads (business_id, customer_id)
    WHERE customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calyrisia_sales_leads_followup
    ON public.calyrisia_sales_leads (business_id, stage, next_follow_up_at);
CREATE INDEX IF NOT EXISTS idx_calyrisia_sales_leads_updated
    ON public.calyrisia_sales_leads (business_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.calyrisia_lead_activities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    lead_id uuid NOT NULL,
    activity_type varchar(40) NOT NULL,
    details text NOT NULL DEFAULT '',
    actor_user_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_calyrisia_lead_activity_tenant
        FOREIGN KEY (lead_id, business_id)
        REFERENCES public.calyrisia_sales_leads(id, business_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_calyrisia_lead_activities_tenant_lead
    ON public.calyrisia_lead_activities (business_id, lead_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.calyrisia_radar_reviews (
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    signal_key varchar(220) NOT NULL,
    state varchar(20) NOT NULL CHECK (state IN ('reviewed','snoozed','dismissed')),
    note text NOT NULL DEFAULT '',
    updated_by uuid,
    expires_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, signal_key)
);

-- These records are served through the authenticated CALYRISIA backend only.
-- Do not add broad anon/authenticated policies; keep direct public REST access blocked.
ALTER TABLE public.calyrisia_sales_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calyrisia_lead_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calyrisia_radar_reviews ENABLE ROW LEVEL SECURITY;
