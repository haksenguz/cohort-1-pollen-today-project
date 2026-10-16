-- Give `created_at` the DEFAULT now() that gen_dmm.py already emits.
--
-- 01_schema.sql is generated from gen_dmm.py, where created() carries
-- default="now()". The live database never got that default, so production and
-- a fresh install were different shapes: the app never noticed, because
-- SQLModel sets these Python-side on every insert, but any raw SQL INSERT had
-- to supply the timestamp by hand or fail on NOT NULL.
--
-- `created_at` is written once and never changes, so a default is simply
-- correct here. On PostgreSQL 11+ SET DEFAULT is metadata-only: it does not
-- rewrite the table and does not take a lock that would block reads or writes.
--
-- updated_at is DELIBERATELY NOT TOUCHED, and the reason matters.
--
-- A default on updated_at would be written at INSERT and then never move
-- again, because there is no trigger. After any UPDATE the row would carry a
-- stale updated_at that is still NOT NULL, still plausible, and still passes
-- every check that exists. Nothing errors. The column would look maintained
-- and would not be — the same class of quiet wrongness as an unrecognised
-- message role or a missing triage verdict.
--
-- That is not hypothetical here: conversations.updated_at is what
-- conversation_service.list_conversations orders by, so a stale value puts the
-- history list in the wrong order and produces no error anywhere. It is a real
-- gap and it is being decided separately - as either a BEFORE UPDATE trigger
-- or an explicit Python-side assignment plus a correction to gen_dmm.py - not
-- papered over with a default that would lie.
--
-- Idempotent by construction: it only touches columns that currently have no
-- default, so re-running is a no-op.


DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'created_at'
          AND column_default IS NULL
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN created_at SET DEFAULT now()',
            t.table_name
        );
        RAISE NOTICE 'set created_at default on %', t.table_name;
    END LOOP;
END $$;