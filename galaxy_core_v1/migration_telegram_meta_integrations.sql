-- CALYRISIA Telegram MTProto + Meta WhatsApp Cloud integration.
-- Safe to execute more than once. The application also applies these columns at startup.

ALTER TABLE public.business_telegram_channels
    ADD COLUMN IF NOT EXISTS auth_mode varchar(20) NOT NULL DEFAULT 'bot',
    ADD COLUMN IF NOT EXISTS phone_number varchar(40),
    ADD COLUMN IF NOT EXISTS session_string text,
    ADD COLUMN IF NOT EXISTS api_id bigint,
    ADD COLUMN IF NOT EXISTS api_hash text;

CREATE TABLE IF NOT EXISTS public.business_meta_channels (
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    platform varchar(20) NOT NULL CHECK (platform IN ('instagram', 'facebook', 'whatsapp')),
    enabled boolean NOT NULL DEFAULT false,
    channel_status varchar(30) NOT NULL DEFAULT 'disconnected',
    account_name varchar(160),
    page_or_ig_id varchar(120),
    access_token text,
    verify_token varchar(160),
    last_error text,
    last_event_at timestamptz,
    connected_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (business_id, platform)
);

ALTER TABLE public.business_meta_channels
    DROP CONSTRAINT IF EXISTS business_meta_channels_platform_check;
ALTER TABLE public.business_meta_channels
    ADD CONSTRAINT business_meta_channels_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'whatsapp'));

CREATE INDEX IF NOT EXISTS idx_meta_channels_provider_account
    ON public.business_meta_channels (platform, page_or_ig_id) WHERE enabled = true;
