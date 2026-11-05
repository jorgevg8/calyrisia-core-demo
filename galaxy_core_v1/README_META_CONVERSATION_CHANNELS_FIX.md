# Fix: Meta webhook conversations channel constraint

The production database may still have an older `conversations_channel_check`
constraint that rejects `facebook` and `instagram`, even though the application
now routes those channels through the omnichannel brain.

This update fixes the constraint in two ways:

1. `app/api/meta_social.py` applies an idempotent schema adjustment during startup
   (and before Meta webhook processing).
2. `migration_meta_conversation_channels.sql` is provided for manual execution if
   the deployment database role does not have permission to alter the table.

The constraint accepts the channels defined by `app.schemas.Channel`. The check is
added `NOT VALID` so pre-existing historical data does not block deployment;
PostgreSQL still checks all new or updated rows.

## Deploy

Commit and push the updated project. After Render redeploys, check the logs for
`Could not expand conversations.channel constraint`. If that warning appears, run
`migration_meta_conversation_channels.sql` in the PostgreSQL SQL editor using a
role that can alter `public.conversations`, then retry with a new incoming Facebook
message.

A successful webhook should no longer emit
`violates check constraint "conversations_channel_check"`.
