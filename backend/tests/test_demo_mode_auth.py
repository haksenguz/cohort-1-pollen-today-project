"""Demo-mode auth fallback (ADR 0003).

When DEMO_MODE=true and the request has no bearer token, get_current_user
returns a known seeded demo user instead of 401. The frontend's phone
preview / demo path uses this so it can hit /api/alerts without going
through the full register/login round-trip.

Out of DEMO_MODE the behaviour is unchanged: no token still 401s.
"""

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user
from app.models import User

DEMO_EMAIL = "demo@local"


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Tests below patch env vars; the lru_cache on get_settings must
    drop the stale Settings so the patch is observed."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_demo_user_if_missing(session) -> None:
    """Run the same idempotent seed as security.get_current_user so the
    test pre-condition matches what the impl produces on a cold start."""
    from sqlalchemy import select

    existing = await session.execute(select(User).where(User.email == DEMO_EMAIL))
    if existing.scalar_one_or_none() is not None:
        return
    session.add(
        User(
            email=DEMO_EMAIL,
            password_hash="!demo-no-login",  # noqa: S106 — placeholder, never valid for login
            latitude=37.5665,
            longitude=126.978,
        )
    )
    await session.commit()


async def test_demo_mode_no_token_returns_demo_user(monkeypatch, session):
    monkeypatch.setenv("DEMO_MODE", "true")
    await _seed_demo_user_if_missing(session)

    user = await get_current_user(session=session, token=None)

    assert user.email == DEMO_EMAIL
    assert user.latitude == pytest.approx(37.5665)
    assert user.longitude == pytest.approx(126.978)


async def test_demo_mode_creates_demo_user_if_missing(monkeypatch, session):
    monkeypatch.setenv("DEMO_MODE", "true")
    # No _seed_demo_user_if_missing — the impl must self-seed.
    user = await get_current_user(session=session, token=None)

    assert user.email == DEMO_EMAIL
    assert user.id is not None


async def test_demo_mode_off_still_401_without_token(monkeypatch, session):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(session=session, token=None)
    assert exc.value.status_code == 401


async def test_demo_mode_with_valid_token_returns_token_user(monkeypatch, session):
    monkeypatch.setenv("DEMO_MODE", "true")
    real_email = "real@example.com"
    real_user = User(
        email=real_email,
        password_hash="x",  # noqa: S106
        latitude=1.0,
        longitude=2.0,
    )
    session.add(real_user)
    await session.commit()
    await session.refresh(real_user)

    token = create_access_token(user_id=real_user.id)
    user = await get_current_user(session=session, token=token)

    assert user.email == real_email
    assert user.id == real_user.id


async def test_demo_mode_with_invalid_token_still_401(monkeypatch, session):
    monkeypatch.setenv("DEMO_MODE", "true")
    with pytest.raises(HTTPException) as exc:
        await get_current_user(session=session, token="not-a-real-token")
    assert exc.value.status_code == 401
