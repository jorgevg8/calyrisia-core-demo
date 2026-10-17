-- CALYRISIA: configuración multinegocio de Telegram para pruebas locales.
-- El arranque de app/main.py aplica estas estructuras automáticamente si la DB permite DDL.

ALTER TABLE public.webchat_payment_requests
    ADD COLUMN IF NOT EXISTS customer_payment_details text;

CREATE TABLE IF NOT EXISTS public.business_telegram_channels (
    business_id uuid PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
    bot_token text NOT NULL,
    bot_username varchar(80),
    owner_chat_id varchar(80),
    enabled boolean NOT NULL DEFAULT false,
    channel_status varchar(20) NOT NULL DEFAULT 'inactive',
    polling_offset bigint NOT NULL DEFAULT 0,
    last_error text,
    last_poll_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_business_telegram_bot_token
    ON public.business_telegram_channels (bot_token);
