-- Constrain messages.role and messages.triage_level to the values this system
-- actually produces.
--
-- Both columns were free text, and both feed safety-critical rendering:
--
--   role          frontend api/types.ts:226 is a CLOSED union "user" | "assistant",
--                 and conversationSession.ts:77 passes it into assistant-ui with no
--                 normalisation. assistant-ui picks the message component BY ROLE,
--                 and the triage banner renders inside AssistantMessage only. So a
--                 role it does not recognise silently drops an EMERGENCY verdict on
--                 resume - no error, no console output, just a missing safety card.
--
--   triage_level  renders on that same banner, and types.ts:58 is the union
--                 "LOW" | "MODERATE" | "EMERGENCY".
--
-- The API contract for `role` is lowercase, which is why the response
-- normalises it. The COLUMN is not lowercase: app/core/enums.py defines
-- MessageRole as USER/ASSISTANT and TriageLevel as LOW/MODERATE/EMERGENCY, and
-- those are what every live row contains. Postgres validates existing rows when
-- ADD CONSTRAINT runs, so a CHECK written against the lowercase API contract
-- would abort on the first row against a real database. The values below are
-- the column's values, not the response's.
--
-- SYSTEM is deliberately NOT permitted. Nothing writes it, and the frontend
-- union has no "system" member, so allowing it would let through a row that
-- renders with no safety banner - the exact silent failure above. Failing at the
-- constraint surfaces the problem instead. gen_dmm.py documented SYSTEM as
-- legal and is corrected to match. Reintroducing it is a deliberate migration
-- that also adds frontend support for it.
--
-- The UPDATEs below are a no-op on any database written only through chat.py.
-- They exist so this migration cannot abort on a row written with different
-- casing by some other path. They will not repair a genuinely unknown value:
-- that still fails the constraint, which is the intended behaviour.


-- 1) Case-normalise before constraining.
UPDATE messages SET role = upper(role) WHERE role <> upper(role);

UPDATE messages
   SET triage_level = upper(triage_level)
 WHERE triage_level IS NOT NULL
   AND triage_level <> upper(triage_level);


-- 2) Add the constraints. Postgres has no ADD CONSTRAINT IF NOT EXISTS, so
--    guard on pg_constraint to keep this re-runnable.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'messages_role_check'
    ) THEN
        ALTER TABLE messages
            ADD CONSTRAINT messages_role_check
            CHECK (role IN ('USER', 'ASSISTANT'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'messages_triage_level_check'
    ) THEN
        ALTER TABLE messages
            ADD CONSTRAINT messages_triage_level_check
            CHECK (triage_level IS NULL OR triage_level IN ('LOW', 'MODERATE', 'EMERGENCY'));
    END IF;
END $$;