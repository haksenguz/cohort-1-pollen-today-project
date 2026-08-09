---
status: applied
owner: Ismoiljon (Slice C)
opened: 2026-08-09
review-by: 2026-09-06
severity: blocker
---

# 0004 — The 07:00 job would have fired and done nothing

## Symptom

None. That is the problem.

The scheduler started, logged `scheduler started — daily-alert at 07:00 KST`,
and registered the job. APScheduler would have "run" it on time. No exception,
no failed `JobRun`, no ops notification. Nothing would have been sent, and every
signal we built to detect failure would have shown green.

Found by reading the FastAPI/async skill guidance against our code, not by a
failing test — nothing was failing.

## Real cause

The job was registered as a lambda:

```python
scheduler.add_job(lambda: container.runner.run(...), CronTrigger(...))
```

APScheduler inspects the callable. A **coroutine function** is awaited; anything
else is called and its return value discarded. A lambda that *returns* a
coroutine is not a coroutine function — so the lambda ran, produced a coroutine
object, and Python dropped it with `RuntimeWarning: coroutine was never awaited`
buried in the logs.

The distinction is between `async def f()` and `lambda: f()`. They look
interchangeable and are not.

## Why it mattered

Milestone 1 (Sun 23 Aug) requires: *"the bot posts a correctly formatted test
alert to one channel, triggered by the scheduler and not by hand."* The manual
CLI path worked perfectly — we had proved idempotency with it — so every test we
had ran the job the one way that was never broken.

This would have been discovered on the milestone, at the worst possible moment,
with a green-looking scheduler.

## What the research says

FastAPI/async guidance is explicit that blocking and async code must not be
mixed carelessly, and that async correctness has to be verified rather than
assumed. The general rule this is an instance of: **when a framework inspects
your callable, wrapping it changes its identity.** The same trap exists with
`functools.partial` over sync/async boundaries and with decorators that lose
`__wrapped__`.

## What we did

Replaced the lambda with a named coroutine function inside `lifespan`, with a
comment stating why it cannot be a lambda:

```python
async def run_daily_alert() -> None:
    await container.runner.run(DAILY_ALERT_JOB, container.daily_alert.execute)

scheduler.add_job(run_daily_alert, CronTrigger(hour=7, minute=0, timezone=KST), ...)
```

Added `tests/test_scheduler_wiring.py` with two tests: one asserting no lambda
is registered in `lifespan`, and one demonstrating the underlying APScheduler
behaviour so the rule is evidence rather than folklore. The second test is
written to fail loudly if a future APScheduler version fixes this, so the rule
can be relaxed deliberately rather than forgotten.

## Evidence

Isolated reproduction before the fix:

```
RESULT: {'lambda': 0, 'coro': 3}
RuntimeWarning: coroutine 'real_job' was never awaited
```

Three seconds, one-second interval: the coroutine function ran three times, the
lambda-wrapped one zero.

After the fix: `22 passed`.

## Still open

Nothing on this bug. The wider gap it exposes: **we have no test that exercises
the scheduled path end to end.** Both remaining triggers — the real cron at
07:00 and a real Telegram send — are still unproven together. The Week-2 task
(Sat 22 Aug) must run the scheduler for real, not the CLI.
