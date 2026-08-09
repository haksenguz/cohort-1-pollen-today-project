from __future__ import annotations

from datetime import UTC, datetime

from pollen.components.alerts.message import build_alert_message
from pollen.libs.enums import (
    KMA_INDEX_TO_RISK_LEVEL,
    RISK_LEVELS_ORDERED,
    PollenType,
    Region,
    RiskLevel,
    risk_at_least,
)
from pollen.libs.kst import kma_bulletin_date, kst_date_plus, kst_today


class TestRiskOrdering:
    def test_is_ordered_low_to_very_high(self) -> None:
        assert [r.value for r in RISK_LEVELS_ORDERED] == [
            "LOW",
            "MODERATE",
            "HIGH",
            "VERY_HIGH",
        ]

    def test_fires_at_or_above_threshold(self) -> None:
        assert risk_at_least(RiskLevel.HIGH, RiskLevel.HIGH)
        assert risk_at_least(RiskLevel.VERY_HIGH, RiskLevel.HIGH)
        assert not risk_at_least(RiskLevel.MODERATE, RiskLevel.HIGH)
        assert not risk_at_least(RiskLevel.LOW, RiskLevel.HIGH)


class TestKstDates:
    def test_rolls_over_at_15_utc_not_midnight_utc(self) -> None:
        # 2026-08-09T15:30Z is 2026-08-10 00:30 in Seoul.
        assert kst_today(datetime(2026, 8, 9, 15, 30, tzinfo=UTC)) == "2026-08-10"

    def test_before_rollover_is_still_the_previous_day(self) -> None:
        assert kst_today(datetime(2026, 8, 9, 14, 30, tzinfo=UTC)) == "2026-08-09"

    def test_adds_whole_days(self) -> None:
        at = datetime(2026, 8, 9, 1, 0, tzinfo=UTC)
        assert kst_date_plus(1, at) == "2026-08-10"
        assert kst_date_plus(3, at) == "2026-08-12"

    def test_bulletin_stamp_to_calendar_date(self) -> None:
        """The stamp says when KMA published, not what the row covers."""
        assert kma_bulletin_date("2026080906") == "2026-08-09"


class TestKmaIndexMapping:
    def test_maps_the_published_integers(self) -> None:
        assert KMA_INDEX_TO_RISK_LEVEL["0"] is RiskLevel.LOW
        assert KMA_INDEX_TO_RISK_LEVEL["3"] is RiskLevel.VERY_HIGH

    def test_empty_string_is_not_a_level(self) -> None:
        """An unpublished slot must never be read as LOW — it would be a fake all-clear."""
        assert "" not in KMA_INDEX_TO_RISK_LEVEL


class TestAlertMessage:
    def test_carries_the_not_medical_advice_line(self) -> None:
        text = build_alert_message(
            region=Region.SEOUL,
            pollen_type=PollenType.WEEDS,
            risk_level=RiskLevel.HIGH,
            target_date="2026-08-10",
        )
        assert "의학적 조언이 아닙니다" in text
        assert "서울특별시" in text
        assert "높음" in text
        assert "8월 10일" in text
