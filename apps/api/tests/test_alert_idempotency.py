"""The guarantee Milestone 2 grades, tested against a real database.

A mocked model would accept two identical inserts and the test would pass while
proving nothing. These run against a real mongod and a real unique index.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pymongo import AsyncMongoClient

from pollen.components.alerts.dto import NewAlert
from pollen.components.alerts.schemas.alert import AlertDoc
from pollen.components.alerts.service import AlertsService
from pollen.libs.enums import PollenType, Region, RiskLevel

pytestmark = pytest.mark.asyncio


def an_alert(**overrides: object) -> NewAlert:
    base = {
        "region": Region.SEOUL,
        "pollen_type": PollenType.WEEDS,
        "target_date": "2026-08-10",
        "risk_level": RiskLevel.HIGH,
        "channel": "@pollen_seoul",
        "sent_at": datetime.now(UTC),
        "message_text": "테스트",
    }
    return NewAlert(**{**base, **overrides})  # type: ignore[arg-type]


async def test_unique_delivery_index_exists(mongo: AsyncMongoClient) -> None:
    """If this index is missing, every other guarantee here is vacuous."""
    info = await mongo.get_default_database()["alerts"].index_information()

    assert "uniq_alert_delivery" in info
    assert info["uniq_alert_delivery"].get("unique") is True
    assert [k for k, _ in info["uniq_alert_delivery"]["key"]] == [
        "channel",
        "region",
        "pollen_type",
        "target_date",
    ]


async def test_second_identical_delivery_is_refused(mongo: AsyncMongoClient) -> None:
    service = AlertsService()

    assert await service.record_delivery(an_alert()) is True
    assert await service.record_delivery(an_alert()) is False

    assert await AlertDoc.find_all().count() == 1


async def test_a_different_target_date_is_allowed(mongo: AsyncMongoClient) -> None:
    service = AlertsService()

    assert await service.record_delivery(an_alert(target_date="2026-08-10")) is True
    assert await service.record_delivery(an_alert(target_date="2026-08-11")) is True

    assert await AlertDoc.find_all().count() == 2


async def test_the_same_day_in_another_region_is_allowed(mongo: AsyncMongoClient) -> None:
    service = AlertsService()

    assert await service.record_delivery(an_alert()) is True
    assert (
        await service.record_delivery(an_alert(region=Region.BUSAN, channel="@pollen_busan"))
        is True
    )

    assert await AlertDoc.find_all().count() == 2


async def test_history_returns_newest_first(mongo: AsyncMongoClient) -> None:
    service = AlertsService()
    await service.record_delivery(
        an_alert(target_date="2026-08-10", sent_at=datetime(2026, 8, 9, 1, tzinfo=UTC))
    )
    await service.record_delivery(
        an_alert(target_date="2026-08-11", sent_at=datetime(2026, 8, 9, 9, tzinfo=UTC))
    )

    page = await service.history(None, limit=10, offset=0)

    assert page.total == 2
    assert page.has_more is False
    assert [i.target_date for i in page.items] == ["2026-08-11", "2026-08-10"]
