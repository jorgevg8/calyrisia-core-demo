-- CALYRISIA / Galaxy Core V1
-- Additive, idempotent migration for demo Webchat payment approval.
-- Safe to run more than once. Does not alter or delete existing tables/data.

CREATE TABLE IF NOT EXISTS public.webchat_payment_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    customer_id uuid NOT NULL REFERENCES public.customers(id) ON DELETE RESTRICT,
    amount numeric(12,2) NOT NULL CHECK (amount > 0),
    currency varchar(10) NOT NULL DEFAULT 'USD',
    payment_method varchar(50) NOT NULL DEFAULT 'binance_demo',
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    source varchar(50) NOT NULL DEFAULT 'webchat_demo',
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    reviewed_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
    order_id uuid REFERENCES public.orders(id) ON DELETE SET NULL,
    approval_note text
);

CREATE INDEX IF NOT EXISTS idx_webchat_payments_business_status_created
    ON public.webchat_payment_requests (business_id, status, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_webchat_payment_order_id
    ON public.webchat_payment_requests (order_id)
    WHERE order_id IS NOT NULL;
