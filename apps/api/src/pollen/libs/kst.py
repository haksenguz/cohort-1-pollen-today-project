"""KST date handling.

Every calendar date in this system is a KST date. The alert job runs at 07:00
KST and forecasts are "tomorrow" in Seoul, not in UTC — so date maths must never
go through the host timezone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), name="KST")


def kst_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(KST)


def kst_today(now: datetime | None = None) -> str:
    """Today's KST calendar date as ``YYYY-MM-DD``."""
    return kst_now(now).strftime("%Y-%m-%d")


def kst_date_plus(days: int, now: datetime | None = None) -> str:
    """The KST calendar date ``days`` from now, as ``YYYY-MM-DD``."""
    return (kst_now(now) + timedelta(days=days)).strftime("%Y-%m-%d")


def kma_bulletin_date(stamp: str) -> str:
    """``YYYYMMDDHH`` bulletin stamp -> its ``YYYY-MM-DD`` KST calendar date.

    The stamp says when KMA published, not what the row covers.
    """
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"
