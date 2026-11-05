-- CALYRISIA: allow all conversation channels accepted by app.schemas.Channel.
-- Safe to run repeatedly. NOT VALID skips scanning historical rows, but PostgreSQL
-- enforces this CHECK for all newly inserted or updated rows.

ALTER TABLE public.conversations
    DROP CONSTRAINT IF EXISTS conversations_channel_check;

ALTER TABLE public.conversations
    ADD CONSTRAINT conversations_channel_check
    CHECK (channel IN (
        'whatsapp',
        'webchat',
        'instagram',
        'facebook',
        'messenger',
        'telegram',
        'email',
        'phone',
        'other'
    )) NOT VALID;
