"""Web push: VAPID key route, subscription upsert and delete, and delivery
that prunes dead endpoints and does nothing without keys.

pywebpush is replaced with a fake, so no test touches the network.
"""

import pytest
from httpx import AsyncClient
from pywebpush import WebPushException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import Settings
from app.models import PushSubscription
from app.services import push as push_service


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


async def _register_and_login(client: AsyncClient, email: str) -> tuple[str, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    token = (await client.post("/api/auth/login", json=payload)).json()["access_token"]
    me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sub_body(endpoint: str, p256dh: str = "p1", auth: str = "a1") -> dict:
    return {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}


def _keys_on(monkeypatch: pytest.MonkeyPatch, **kwargs) -> None:
    base = {"vapid_public_key": "PUB", "vapid_private_key": "PRIV"}
    base.update(kwargs)
    fake = Settings(**base)
    monkeypatch.setattr("app.services.push.get_settings", lambda: fake)
    monkeypatch.setattr("app.api.push.get_settings", lambda: fake)


@pytest.mark.asyncio
async def test_vapid_key_is_null_when_unconfigured(client: AsyncClient, monkeypatch) -> None:
    _keys_on(monkeypatch, vapid_public_key=None, vapid_private_key=None)
    res = await client.get("/api/push/vapid-key")
    assert res.status_code == 200
    assert res.json() == {"public_key": None}


@pytest.mark.asyncio
async def test_vapid_key_is_returned_when_set(client: AsyncClient, monkeypatch) -> None:
    _keys_on(monkeypatch)
    res = await client.get("/api/push/vapid-key")
    assert res.json() == {"public_key": "PUB"}


@pytest.mark.asyncio
async def test_subscribe_requires_a_token(client: AsyncClient) -> None:
    res = await client.post("/api/push/subscribe", json=_sub_body("https://push.example/1"))
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_subscribe_upserts_by_endpoint(client: AsyncClient, session: AsyncSession) -> None:
    token, user_id = await _register_and_login(client, "push1@example.com")
    url = "https://push.example/dev-1"

    first = await client.post(
        "/api/push/subscribe", json=_sub_body(url, "p1", "a1"), headers=_auth(token)
    )
    assert first.status_code == 204
    second = await client.post(
        "/api/push/subscribe", json=_sub_body(url, "p2", "a2"), headers=_auth(token)
    )
    assert second.status_code == 204

    rows = (await session.execute(select(PushSubscription))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == user_id
    assert (rows[0].p256dh, rows[0].auth) == ("p2", "a2")


@pytest.mark.asyncio
async def test_delete_removes_only_the_callers_subscription(
    client: AsyncClient, session: AsyncSession
) -> None:
    token_a, _ = await _register_and_login(client, "push-a@example.com")
    token_b, _ = await _register_and_login(client, "push-b@example.com")
    url = "https://push.example/shared"
    await client.post("/api/push/subscribe", json=_sub_body(url), headers=_auth(token_a))

    # Another user cannot remove it.
    other = await client.request(
        "DELETE", "/api/push/subscribe", json={"endpoint": url}, headers=_auth(token_b)
    )
    assert other.status_code == 204
    assert len((await session.execute(select(PushSubscription))).scalars().all()) == 1

    own = await client.request(
        "DELETE", "/api/push/subscribe", json={"endpoint": url}, headers=_auth(token_a)
    )
    assert own.status_code == 204
    assert (await session.execute(select(PushSubscription))).scalars().all() == []


@pytest.mark.asyncio
async def test_send_prunes_gone_endpoints_and_keeps_live_ones(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _keys_on(monkeypatch)
    token, user_id = await _register_and_login(client, "push-send@example.com")
    await client.post(
        "/api/push/subscribe", json=_sub_body("https://gone.example"), headers=_auth(token)
    )
    await client.post(
        "/api/push/subscribe", json=_sub_body("https://live.example"), headers=_auth(token)
    )

    sent: list[str] = []

    def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
        endpoint = subscription_info["endpoint"]
        sent.append(endpoint)
        if endpoint == "https://gone.example":
            raise WebPushException("expired", response=_Resp(410))

    monkeypatch.setattr(push_service, "webpush", fake_webpush)
    await push_service.send_push(session, user_id, "Alert", "Pollen is high")

    assert sorted(sent) == ["https://gone.example", "https://live.example"]
    remaining = (await session.execute(select(PushSubscription))).scalars().all()
    assert [r.endpoint for r in remaining] == ["https://live.example"]


@pytest.mark.asyncio
async def test_send_is_a_noop_without_keys(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _keys_on(monkeypatch, vapid_public_key=None, vapid_private_key=None)
    token, user_id = await _register_and_login(client, "push-nokeys@example.com")
    await client.post(
        "/api/push/subscribe", json=_sub_body("https://x.example"), headers=_auth(token)
    )

    calls: list[str] = []
    monkeypatch.setattr(push_service, "webpush", lambda **kw: calls.append("x"))
    await push_service.send_push(session, user_id, "Alert", "body")
    assert calls == []


@pytest.mark.asyncio
async def test_send_keeps_subscription_on_other_failures(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _keys_on(monkeypatch)
    token, user_id = await _register_and_login(client, "push-fail@example.com")
    await client.post(
        "/api/push/subscribe", json=_sub_body("https://flaky.example"), headers=_auth(token)
    )

    def boom(**kwargs):
        raise WebPushException("server error", response=_Resp(500))

    monkeypatch.setattr(push_service, "webpush", boom)
    await push_service.send_push(session, user_id, "Alert", "body")
    # A 500 is not a dead endpoint, so the subscription stays.
    assert len((await session.execute(select(PushSubscription))).scalars().all()) == 1
