-- Additive columns introduced after the initial schema was generated.
--
-- backend/db/init/01_schema.sql is regenerated from docs/erd/gen_dmm.py and
-- only ever describes a FRESH database. These three columns were added to the
-- models and to gen_dmm.py, but any database that already existed kept the old
-- shape: `conversations` had no `title`, and `messages` had no triage columns.
--
-- That is not theoretical. `_persist_turn` writes Message.triage_level and
-- Message.triage_reasons on every assistant turn, and the conversations
-- endpoints select Conversation.title, so against an unpatched database the
-- chat stream fails at persistence and the list endpoint raises
-- "column conversations.title does not exist".
--
-- Every statement is idempotent, so this is safe to run more than once.

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS title VARCHAR(200);

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS triage_level VARCHAR(12);

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS triage_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;