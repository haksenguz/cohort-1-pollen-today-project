"""Tests for app/core/rate_limit.py.

The limiter is a billing control on `POST /api/chat`: every turn is a real
model call, so an unbounded endpoint is a direct cost risk. These tests pin
the behaviour that actually stops a runaway loop — including the concurrent
case, which is the one a naive implementation silently gets wrong.
"""

import asyncio

import pytest

from app.core.rate_limit import RATE_LIMIT_PER_MINUTE, WINDOW_SECONDS, InMemoryRateLimiter

# ---------------------------------------------------------------------------
# The limiter itself.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requests_under_the_limit_are_allowed():
    limiter = InMemoryRateLimiter(limit_per_minute=3)

    for _ in range(3):
        decision = await limiter.check("user-1")

        assert decision.allowed is True

    assert decision.remaining == 0


@pytest.mark.asyncio
async def test_the_request_over_the_limit_is_refused():
    limiter = InMemoryRateLimiter(limit_per_minute=2)

    await limiter.check("u")
    await limiter.check("u")
    decision = await limiter.check("u")

    assert decision.allowed is False
    assert decision.remaining == 0
    assert decision.retry_after_seconds > 0


@pytest.mark.asyncio
async def test_limit_is_per_user_not_global():
    """One user exhausting their window must not block anyone else."""
    limiter = InMemoryRateLimiter(limit_per_minute=1)

    assert (await limiter.check("noisy")).allowed is True
    assert (await limiter.check("noisy")).allowed is False
    # A different user is unaffected.
    assert (await limiter.check("quiet")).allowed is True


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_overrun_the_limit():
    """The failure this guards: N simultaneous requests each read "one slot
    left" and each take it, so the limit is exceeded by a burst.

    All ten fire together with no await between the check and the append, so
    without the lock this reliably admits all ten.
    """
    limiter = InMemoryRateLimiter(limit_per_minute=3)

    decisions = await asyncio.gather(*(limiter.check("burst") for _ in range(10)))

    allowed = [d for d in decisions if d.allowed]
    assert len(allowed) == 3, f"expected exactly 3 admitted, got {len(allowed)}"


@pytest.mark.asyncio
async def test_hits_aged_out_of_the_window_are_forgotten(monkeypatch):
    """A sliding window, not a fixed bucket: after the window passes, the user
    is allowed again without waiting for a clock tick."""
    limiter = InMemoryRateLimiter(limit_per_minute=1)
    now = 1000.0
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: now)

    assert (await limiter.check("u")).allowed is True
    assert (await limiter.check("u")).allowed is False

    now += WINDOW_SECONDS + 1

    assert (await limiter.check("u")).allowed is True


@pytest.mark.asyncio
async def test_retry_after_reflects_when_a_slot_frees_up(monkeypatch):
    """The client needs an accurate hint, not a fixed guess."""
    now = 1000.0
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: now)
    limiter = InMemoryRateLimiter(limit_per_minute=1)

    await limiter.check("u")
    now += 45  # 15s left in the window
    decision = await limiter.check("u")

    assert decision.allowed is False
    assert 14 <= decision.retry_after_seconds <= 16


@pytest.mark.asyncio
async def test_a_non_positive_limit_disables_limiting():
    """The escape hatch for local dev and the test suite."""
    limiter = InMemoryRateLimiter(limit_per_minute=0)

    for _ in range(50):
        assert (await limiter.check("u")).allowed is True


@pytest.mark.asyncio
async def test_reset_clears_one_key_or_all_of_them():
    limiter = InMemoryRateLimiter(limit_per_minute=1)
    await limiter.check("a")
    await limiter.check("b")

    await limiter.reset("a")
    assert (await limiter.check("a")).allowed is True
    assert (await limiter.check("b")).allowed is False

    await limiter.reset()
    assert (await limiter.check("b")).allowed is True


# ---------------------------------------------------------------------------
# Headers, which the frontend and any client reads.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowed_response_carries_remaining_budget():
    limiter = InMemoryRateLimiter(limit_per_minute=3)

    decision = await limiter.check("u")

    assert decision.headers["X-RateLimit-Limit"] == "3"
    assert decision.headers["X-RateLimit-Remaining"] == "2"
    assert "Retry-After" not in decision.headers


@pytest.mark.asyncio
async def test_refused_response_carries_retry_after():
    limiter = InMemoryRateLimiter(limit_per_minute=1)
    await limiter.check("u")

    decision = await limiter.check("u")

    # Whole seconds, at least 1, so a client can parse it.
    assert int(decision.headers["Retry-After"]) >= 1
    assert decision.headers["X-RateLimit-Remaining"] == "0"


def test_default_limit_is_a_conversation_not_a_firehose():
    """A real intake conversation is a handful of turns; the default must not
    get in a genuine user's way, only a runaway loop's."""
    assert 5 <= RATE_LIMIT_PER_MINUTE <= 60
