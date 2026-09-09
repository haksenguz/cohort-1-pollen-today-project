"""Alerts and notification preferences over HTTP.

Every route is scoped to the authenticated user, so the tests that matter are
the ones proving one user cannot see or touch another's data.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AlertType, RiskLevel
from app.models import Alert


async def _register_and_login(client: AsyncClient, email: str) -> tuple[str, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    token = (await client.post("/api/auth/login", json=payload)).json()["access_token"]
    me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_alerts_require_a_token(client: AsyncClient) -> None:
    assert (await client.get("/api/alerts")).status_code == 401


@pytest.mark.asyncio
async def test_preferences_require_a_token(client: AsyncClient) -> None:
    assert (await client.get("/api/notifications/preferences")).status_code == 401


@pytest.mark.asyncio
async def test_preferences_are_created_on_first_read(client: AsyncClient) -> None:
    token, _ = await _register_and_login(client, "first@example.com")
    res = await client.get("/api/notifications/preferences", headers=_auth(token))

    assert res.status_code == 200
    body = res.json()
    assert body["alert_pollen"] is True
    assert body["min_risk_level"] == "MODERATE"
    assert body["quiet_hours_start"] is None


@pytest.mark.asyncio
async def test_updating_preferences_round_trips(client: AsyncClient) -> None:
    token, _ = await _register_and_login(client, "prefs@example.com")

    res = await client.put(
        "/api/notifications/preferences",
        json={
            "alert_pollen": False,
            "min_risk_level": "HIGH",
            "quiet_hours_start": 22,
            "quiet_hours_end": 7,
        },
        headers=_auth(token),
    )
    assert res.status_code == 200

    body = (await client.get("/api/notifications/preferences", headers=_auth(token))).json()
    assert body["alert_pollen"] is False
    assert body["min_risk_level"] == "HIGH"
    assert body["quiet_hours_start"] == 22
    assert body["quiet_hours_end"] == 7


@pytest.mark.asyncio
async def test_an_out_of_range_quiet_hour_is_rejected(client: AsyncClient) -> None:
    token, _ = await _register_and_login(client, "range@example.com")
    res = await client.put(
        "/api/notifications/preferences",
        json={"quiet_hours_start": 24},
        headers=_auth(token),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_a_user_only_sees_their_own_alerts(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner_token, owner_id = await _register_and_login(client, "owner2@example.com")
    other_token, other_id = await _register_and_login(client, "other2@example.com")

    session.add(
        Alert(
            user_id=owner_id,
            alert_type=AlertType.POLLEN,
            risk_level=RiskLevel.HIGH,
            message="High tree pollen today",
        )
    )
    session.add(
        Alert(
            user_id=other_id,
            alert_type=AlertType.AIR_QUALITY,
            risk_level=RiskLevel.MODERATE,
            message="Air quality dropping",
        )
    )
    await session.commit()

    owner_alerts = (await client.get("/api/alerts", headers=_auth(owner_token))).json()
    assert len(owner_alerts) == 1
    assert owner_alerts[0]["message"] == "High tree pollen today"

    other_alerts = (await client.get("/api/alerts", headers=_auth(other_token))).json()
    assert len(other_alerts) == 1
    assert other_alerts[0]["alert_type"] == "AIR_QUALITY"


@pytest.mark.asyncio
async def test_cannot_mark_someone_elses_alert_read(
    client: AsyncClient, session: AsyncSession
) -> None:
    _, owner_id = await _register_and_login(client, "owner3@example.com")
    intruder_token, _ = await _register_and_login(client, "intruder3@example.com")

    alert = Alert(
        user_id=owner_id,
        alert_type=AlertType.POLLEN,
        risk_level=RiskLevel.HIGH,
        message="not yours",
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)

    res = await client.patch(f"/api/alerts/{alert.id}/read", headers=_auth(intruder_token))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_marking_your_own_alert_read(client: AsyncClient, session: AsyncSession) -> None:
    token, user_id = await _register_and_login(client, "reader@example.com")

    alert = Alert(
        user_id=user_id,
        alert_type=AlertType.WEATHER,
        risk_level=RiskLevel.MODERATE,
        message="Windy",
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)

    assert (
        await client.patch(f"/api/alerts/{alert.id}/read", headers=_auth(token))
    ).status_code in (
        200,
        204,
    )

    alerts = (await client.get("/api/alerts", headers=_auth(token))).json()
    assert alerts[0]["is_read"] is True
