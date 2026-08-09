"""Regression test for a bug that would have failed Milestone 1 silently.

APScheduler inspects the callable it is given. A coroutine FUNCTION is awaited;
anything else is called and its return value discarded. Registering
``lambda: some_async_thing()`` therefore produces a job that runs on schedule,
does nothing, raises no error and records no failure.

The scheduler looks healthy. The alert never sends.
"""

from __future__ import annotations

import asyncio
import inspect

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from pollen.main import lifespan


def test_lifespan_registers_a_coroutine_function() -> None:
    """The scheduled callable must be awaitable by APScheduler.

    Reads the closure of ``lifespan`` rather than starting the app, so this
    needs no database.
    """
    inner = lifespan.__wrapped__ if hasattr(lifespan, "__wrapped__") else lifespan
    names = inner.__code__.co_consts

    scheduled = [
        c for c in names if inspect.iscode(c) and c.co_name in {"run_daily_alert", "<lambda>"}
    ]

    assert scheduled, "no scheduled callable found in lifespan"
    assert all(c.co_name != "<lambda>" for c in scheduled), (
        "a lambda is registered with APScheduler; it will never be awaited"
    )


async def test_apscheduler_drops_lambda_wrapped_coroutines() -> None:
    """Proves the underlying behaviour, so the rule above is not folklore."""
    hits = {"lambda": 0, "coro": 0}

    async def bump(key: str) -> None:
        hits[key] += 1

    async def wrapper() -> None:
        await bump("coro")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: bump("lambda"), IntervalTrigger(seconds=1), id="l")
    scheduler.add_job(wrapper, IntervalTrigger(seconds=1), id="c")
    scheduler.start()
    await asyncio.sleep(2.5)
    scheduler.shutdown(wait=False)

    assert hits["coro"] >= 1, "a coroutine function should have run"
    assert hits["lambda"] == 0, (
        "if this now passes, APScheduler changed and the rule can be relaxed"
    )
