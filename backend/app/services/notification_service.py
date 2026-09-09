"""Scheduled environment checks that turn crossed risk thresholds into
stored `Alert` rows (documentation §15, "Notification Architecture").

This module only *generates* alerts. It never sends anything (no email, no
push, no SMS) — delivery is out of scope. It reuses the deterministic
`risk.score()` from `app/services/risk.py` (read-only dependency, not
modified here) so alert thresholds stay consistent with `/api/environment`.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.enums import AlertType, PollenLevel, RiskLevel
from app.models import Alert, EnvironmentSnapshot, NotificationPreference, User, UserAllergy
from app.services import air_quality_service as aqs
from app.services import pollen_service as ps
from app.services import risk
from app.services import weather_service as ws

logger = logging.getLogger(__name__)

# How often the scheduler re-runs the check across all users.
CHECK_INTERVAL_MINUTES = 60

# Don't re-alert a user for the same alert_type/risk_level combination more
# often than this. Prevents spamming the same "HIGH pollen" alert every hour.
ALERT_COOLDOWN_HOURS = 6

_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.EMERGENCY: 3,
}

_POLLEN_RANK = {PollenLevel.LOW: 0, PollenLevel.MODERATE: 1, PollenLevel.HIGH: 2}

_POLLEN_ALLERGENS = {
    "TREE_POLLEN": "tree_pollen",
    "GRASS_POLLEN": "grass_pollen",
    "WEED_POLLEN": "weed_pollen",
}


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


async def get_or_create_preferences(session: AsyncSession, user_id: int) -> NotificationPreference:
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    pref = result.scalars().first()
    if pref is not None:
        return pref
    pref = NotificationPreference(user_id=user_id)
    session.add(pref)
    await session.commit()
    await session.refresh(pref)
    return pref


# ---------------------------------------------------------------------------
# Threshold / quiet-hours logic
# ---------------------------------------------------------------------------


def _in_quiet_hours(pref: NotificationPreference, now: datetime) -> bool:
    start, end = pref.quiet_hours_start, pref.quiet_hours_end
    if start is None or end is None:
        return False
    hour = now.hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    # wraps past midnight, e.g. 22 -> 7
    return hour >= start or hour < end


def _alert_type_enabled(pref: NotificationPreference, alert_type: AlertType) -> bool:
    return {
        AlertType.POLLEN: pref.alert_pollen,
        AlertType.AIR_QUALITY: pref.alert_air_quality,
        AlertType.WEATHER: pref.alert_weather,
        AlertType.GENERAL: True,
    }.get(alert_type, True)


def should_generate_alert(
    pref: NotificationPreference,
    alert_type: AlertType,
    risk_level: RiskLevel,
    now: datetime | None = None,
) -> bool:
    """Whether an alert should be raised for this user right now, purely from
    their stored preferences. Does not consult the database (no cooldown
    check here — that's `generate_alert_for_user`'s job, since it needs a
    session)."""
    now = now or _now()
    min_level = RiskLevel(pref.min_risk_level)
    if _RISK_ORDER[risk_level] < _RISK_ORDER[min_level]:
        return False
    if not _alert_type_enabled(pref, alert_type):
        return False
    if _in_quiet_hours(pref, now):
        return False
    return True


def dominant_alert_type(env: risk.EnvInput, user_allergens: set[str]) -> AlertType:
    """Best-effort label for *why* the risk crossed the threshold, used only
    to pick the alert's `alert_type` and preference toggle — not part of the
    risk score itself."""
    pollen_levels = [env.tree_pollen, env.grass_pollen, env.weed_pollen]
    best_pollen = max((_POLLEN_RANK.get(p, 0) for p in pollen_levels), default=0)

    matches_allergen = any(
        _POLLEN_RANK.get(getattr(env, col), 0) >= 1
        for allergen, col in _POLLEN_ALLERGENS.items()
        if allergen in user_allergens
    )
    if best_pollen >= 1 and (matches_allergen or not user_allergens):
        return AlertType.POLLEN

    if (env.pm25 is not None and env.pm25 >= 15) or (env.pm10 is not None and env.pm10 >= 80):
        return AlertType.AIR_QUALITY

    if env.wind_speed is not None and env.wind_speed >= 5:
        return AlertType.WEATHER

    return AlertType.GENERAL


def build_alert_message(risk_level: RiskLevel, alert_type: AlertType, env: risk.EnvInput) -> str:
    if alert_type == AlertType.POLLEN:
        level = max(
            [env.tree_pollen, env.grass_pollen, env.weed_pollen],
            key=lambda p: _POLLEN_RANK.get(p, 0),
        )
        return (
            f"{risk_level.value.title()} pollen risk today. Pollen levels are "
            f"{level.value.lower() if level else 'elevated'} in your area. Consider "
            "reducing prolonged outdoor exposure and following your usual "
            "allergy-management plan."
        )
    if alert_type == AlertType.AIR_QUALITY:
        return (
            f"{risk_level.value.title()} air quality risk today. PM2.5/PM10 levels "
            "are elevated in your area. Consider limiting outdoor activity."
        )
    if alert_type == AlertType.WEATHER:
        return (
            f"{risk_level.value.title()} weather-related risk today. High winds can "
            "carry more pollen and irritants. Take usual precautions."
        )
    return f"{risk_level.value.title()} environmental risk today in your area."


# ---------------------------------------------------------------------------
# Alert generation
# ---------------------------------------------------------------------------


async def _recent_duplicate_exists(
    session: AsyncSession,
    user_id: int,
    alert_type: AlertType,
    risk_level: RiskLevel,
    now: datetime,
) -> bool:
    from datetime import timedelta

    cutoff = now - timedelta(hours=ALERT_COOLDOWN_HOURS)
    result = await session.execute(
        select(Alert).where(
            Alert.user_id == user_id,
            Alert.alert_type == alert_type.value,
            Alert.risk_level == risk_level.value,
            Alert.created_at >= cutoff,
        )
    )
    return result.scalars().first() is not None


async def generate_alert_for_user(
    session: AsyncSession,
    user: User,
    env: risk.EnvInput,
    environment_snapshot_id: int | None = None,
    now: datetime | None = None,
) -> Alert | None:
    """Evaluate one user's risk against current environment data and, if
    warranted, write and return a new `Alert`. Returns None if no alert was
    generated (risk below threshold, preference disabled, quiet hours, or a
    recent duplicate already exists)."""
    now = now or _now()

    allergy_result = await session.execute(
        select(UserAllergy.allergen).where(UserAllergy.user_id == user.id)
    )
    user_allergens = {row for row in allergy_result.scalars().all()}

    _, risk_level = risk.score(env, user_allergens)
    alert_type = dominant_alert_type(env, user_allergens)

    pref = await get_or_create_preferences(session, user.id)
    if not should_generate_alert(pref, alert_type, risk_level, now):
        return None
    if await _recent_duplicate_exists(session, user.id, alert_type, risk_level, now):
        return None

    alert = Alert(
        user_id=user.id,
        environment_snapshot_id=environment_snapshot_id,
        risk_level=risk_level.value,
        alert_type=alert_type.value,
        message=build_alert_message(risk_level, alert_type, env),
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# Fetching environment data (mirrors app/api/environment.py's provider
# fan-out; kept local so this module doesn't depend on that router).
# ---------------------------------------------------------------------------


@dataclass
class _FetchedEnvironment:
    env: risk.EnvInput
    snapshot: EnvironmentSnapshot


async def _fetch_environment(lat: float, lon: float) -> _FetchedEnvironment:
    import httpx

    from app.core.config import get_settings

    key = get_settings().pollen_api_key
    async with httpx.AsyncClient() as http_client:
        weather = await ws.fetch_weather(lat, lon, http_client)
        air = await aqs.fetch_air_quality(lat, lon, http_client)
        pollen = await ps.fetch_pollen(lat, lon, key)

    env = risk.EnvInput(
        tree_pollen=pollen.tree,
        grass_pollen=pollen.grass,
        weed_pollen=pollen.weed,
        pm25=air.pm25,
        pm10=air.pm10,
        wind_speed=weather.wind_speed,
    )
    _, risk_level = risk.score(env)
    snapshot = EnvironmentSnapshot(
        latitude=lat,
        longitude=lon,
        tree_pollen=pollen.tree.value if pollen.tree else None,
        grass_pollen=pollen.grass.value if pollen.grass else None,
        weed_pollen=pollen.weed.value if pollen.weed else None,
        pm25=air.pm25,
        pm10=air.pm10,
        temperature=weather.temperature,
        humidity=weather.humidity,
        wind_speed=weather.wind_speed,
        risk_level=risk_level.value,
    )
    return _FetchedEnvironment(env=env, snapshot=snapshot)


async def run_environmental_checks(
    session: AsyncSession, now: datetime | None = None
) -> list[Alert]:
    """The scheduled job: for every user with a known location, fetch fresh
    environment data, score their personal risk, and write an Alert when it
    crosses their threshold. Users sharing a rounded lat/lon fetch the
    environment once."""
    now = now or _now()

    result = await session.execute(
        select(User).where(User.latitude.is_not(None), User.longitude.is_not(None))
    )
    users = list(result.scalars().all())

    cache: dict[tuple[float, float], _FetchedEnvironment] = {}
    alerts: list[Alert] = []

    for user in users:
        key = (round(user.latitude, 2), round(user.longitude, 2))
        fetched = cache.get(key)
        if fetched is None:
            try:
                fetched = await _fetch_environment(user.latitude, user.longitude)
            except Exception:
                logger.warning(
                    "environment fetch failed for lat=%s lon=%s",
                    user.latitude,
                    user.longitude,
                    exc_info=True,
                )
                continue
            session.add(fetched.snapshot)
            await session.commit()
            await session.refresh(fetched.snapshot)
            cache[key] = fetched

        alert = await generate_alert_for_user(session, user, fetched.env, fetched.snapshot.id, now)
        if alert is not None:
            alerts.append(alert)

    return alerts


# ---------------------------------------------------------------------------
# Scheduler wiring (APScheduler). See start_scheduler() docstring for why.
# ---------------------------------------------------------------------------

_scheduler = None


async def _scheduled_job() -> None:
    """Wrapper run by APScheduler. Never raises — a failed check must not
    take down the scheduler loop, matching the non-fatal spirit of
    `init_db()` in app/main.py."""
    from app.core.db import async_session

    try:
        async with async_session() as session:
            alerts = await run_environmental_checks(session)
            if alerts:
                logger.info("scheduled environmental check generated %d alert(s)", len(alerts))
    except Exception:
        logger.warning("scheduled environmental check failed", exc_info=True)


def start_scheduler():
    """Start the background scheduler that periodically runs
    `run_environmental_checks` for every user with a stored location.

    Chosen: APScheduler's `AsyncIOScheduler`. It runs in-process on the same
    event loop FastAPI already uses — no extra worker process, no broker
    (Redis/Celery is the documented "larger deployment" option, overkill for
    this MVP's single periodic job). `start()` schedules work on the running
    loop and returns immediately, so it never blocks app startup, and a job
    that raises is swallowed by `_scheduled_job` so one bad run can't crash
    the scheduler or the API.

    Returns None (does not start anything) if APScheduler isn't installed,
    so a missing optional dependency degrades instead of blocking startup.
    """
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("apscheduler not installed; scheduled environmental checks disabled")
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_job,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        id="environmental_check",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
