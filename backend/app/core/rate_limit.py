"""Per-user rate limiting for the chat endpoint.

Every turn of the symptom conversation costs a real model call, so the chat
endpoint is the one place in this app where abuse has a direct cost attached.
Without a limit, one authenticated client can loop `POST /api/chat` and bill
the OpenRouter key at will. Auth alone is not a control: a signed-up user is
exactly the thing being protected from.

Design notes:

- **In-process, per-user, sliding window.** No new table, no Redis, no schema
  change, so nothing here touches the ERD or the generated SQL. The state is a
  `deque` of timestamps per user id in this process's memory.
- **The limitation is real and is not hidden**: this is per-process, so N
  uvicorn workers would each allow the limit, and a restart clears it. For a
  single-instance app that is the correct trade — a shared store is the
  "larger deployment" answer noted in `notification_service`, not a
  prerequisite for this. See `README` note in TASKS.md parking lot.
- **Thread- and task-safe.** An `asyncio.Lock` guards the window mutation so
  two concurrent requests from the same user cannot both read "one slot left"
  and both take it.

`RATE_LIMIT_PER_MINUTE` of 0 or less disables limiting entirely, which is the
escape hatch for local development and for tests that drive many turns.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass

# Default: a real conversation is a handful of turns a minute. 20 leaves room
# for a fast or multi-device user and still caps a runaway loop at a twentieth
# of the bill.
RATE_LIMIT_PER_MINUTE = 20

WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class RateLimitDecision:
    """The outcome of one check. `allowed=False` carries the retry hint."""

    allowed: bool
    remaining: int
    limit: int
    retry_after_seconds: float

    @property
    def headers(self) -> dict[str, str]:
        """Standard rate-limit headers, so a client can back off sensibly."""
        h = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
        }
        if not self.allowed:
            h["Retry-After"] = str(max(int(self.retry_after_seconds) + 1, 1))
        return h


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by an arbitrary string (we use user id)."""

    def __init__(self, limit_per_minute: int = RATE_LIMIT_PER_MINUTE) -> None:
        self._limit = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    @property
    def limit(self) -> int:
        return self._limit

    async def check(self, key: str) -> RateLimitDecision:
        """Record a hit for `key` and say whether it is allowed.

        A non-positive limit means "no limit", which is what local dev and the
        test suite use.
        """
        if self._limit <= 0:
            return RateLimitDecision(allowed=True, remaining=0, limit=0, retry_after_seconds=0.0)

        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS

        async with self._lock:
            window = self._hits[key]
            # Drop everything that has aged out of the window.
            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= self._limit:
                # Oldest hit still in the window sets when a slot frees up.
                retry_after = (window[0] + WINDOW_SECONDS) - now
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    limit=self._limit,
                    retry_after_seconds=retry_after,
                )

            window.append(now)
            return RateLimitDecision(
                allowed=True,
                remaining=self._limit - len(window),
                limit=self._limit,
                retry_after_seconds=0.0,
            )

    async def reset(self, key: str | None = None) -> None:
        """Forget one key's window, or everything. Used by tests."""
        async with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


_limiter: InMemoryRateLimiter | None = None
_limiter_lock = asyncio.Lock()


def get_limiter() -> InMemoryRateLimiter:
    """The process-wide limiter, created on first use.

    Lazy so importing this module has no side effects, which keeps the test
    suite able to swap in a fresh limiter per test.
    """
    global _limiter
    if _limiter is None:
        from app.core.config import get_settings

        _limiter = InMemoryRateLimiter(limit_per_minute=get_settings().chat_rate_limit_per_minute)
    return _limiter


def set_limiter(limiter: InMemoryRateLimiter | None) -> None:
    """Install (or clear) the process-wide limiter. Tests call this."""
    global _limiter
    _limiter = limiter
