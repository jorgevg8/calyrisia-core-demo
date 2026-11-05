-- CALYRISIA commercial tiers and tenant-specific operational dashboard.
-- Idempotent: safe to apply more than once.
ALTER TABLE public.businesses
    ADD COLUMN IF NOT EXISTS plan_code varchar(30) NOT NULL DEFAULT 'emprendedor';
ALTER TABLE public.businesses
    ADD COLUMN IF NOT EXISTS webchat_enabled boolean NOT NULL DEFAULT false;

UPDATE public.businesses
SET plan_code = 'emprendedor'
WHERE plan_code IS NULL OR plan_code NOT IN ('emprendedor', 'smart_business', 'enterprise');

CREATE TABLE IF NOT EXISTS public.business_ai_usage_monthly (
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    month_start date NOT NULL,
    response_count integer NOT NULL DEFAULT 0 CHECK (response_count >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, month_start)
);

CREATE TABLE IF NOT EXISTS public.product_images (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    image_url text NOT NULL,
    position integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (length(image_url) <= 2048)
);
CREATE INDEX IF NOT EXISTS idx_product_images_tenant_product
    ON public.product_images (business_id, product_id, position);

CREATE TABLE IF NOT EXISTS public.business_bookings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    booking_type varchar(20) NOT NULL CHECK (booking_type IN ('appointment', 'reservation')),
    customer_name varchar(200) NOT NULL,
    customer_phone varchar(80),
    party_size integer NOT NULL DEFAULT 1 CHECK (party_size >= 1 AND party_size <= 200),
    starts_at timestamptz NOT NULL,
    service_name varchar(200) NOT NULL,
    table_number varchar(30),
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled')),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_business_bookings_tenant_start
    ON public.business_bookings (business_id, booking_type, starts_at);


CREATE TABLE IF NOT EXISTS public.business_payment_instructions (
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    method_code varchar(30) NOT NULL CHECK (method_code IN ('pago_movil','binance')),
    enabled boolean NOT NULL DEFAULT false,
    instructions text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, method_code),
    CHECK (length(instructions) <= 3000)
);


CREATE TABLE IF NOT EXISTS public.business_dashboard_settings (
    business_id uuid PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
    restaurant_table_count integer NOT NULL DEFAULT 12 CHECK (restaurant_table_count BETWEEN 1 AND 100),
    updated_at timestamptz NOT NULL DEFAULT now()
);
