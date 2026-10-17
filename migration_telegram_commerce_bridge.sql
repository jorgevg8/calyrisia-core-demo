-- CALYRISIA Telegram commerce bridge — additive/idempotent.
-- The bot tracks its Telegram user ID separately from the customer's actual phone.
-- Payment screenshots remain pending for manual verification; no auto-approval is added.

CREATE TABLE IF NOT EXISTS public.telegram_customer_sessions (
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    telegram_user_id varchar(80) NOT NULL,
    chat_id varchar(80) NOT NULL,
    customer_id uuid REFERENCES public.customers(id) ON DELETE SET NULL,
    conversation_id uuid REFERENCES public.conversations(id) ON DELETE SET NULL,
    telegram_username varchar(255),
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, telegram_user_id)
);

CREATE INDEX IF NOT EXISTS idx_telegram_sessions_customer
    ON public.telegram_customer_sessions (business_id, customer_id);

CREATE TABLE IF NOT EXISTS public.telegram_update_events (
    update_id bigint PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    received_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telegram_update_events_business
    ON public.telegram_update_events (business_id, received_at DESC);
