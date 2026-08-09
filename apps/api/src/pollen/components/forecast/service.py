from __future__ import annotations

from datetime import UTC, datetime

from pollen.components.forecast.dto import ForecastDayDTO, ForecastDTO
from pollen.libs.enums import PollenType, Region, RiskLevel
from pollen.libs.kst import kst_date_plus


class ForecastService:
    """Slice A — Forecast Engine. Owner: Jamshid.

    STUB. Shipped by the tech lead so Slice C can build and test the alert job
    against a live query before Slice A exists. Jamshid replaces the body with
    the persistence baseline (tomorrow equals today), then the trained model.
    The SDL does not change when he does.
    """

    def three_day(self, region: Region, pollen_type: PollenType) -> ForecastDTO:
        return ForecastDTO(
            region=region,
            pollen_type=pollen_type,
            days=[
                ForecastDayDTO(
                    date=kst_date_plus(offset),
                    risk_level=RiskLevel.MODERATE,
                    confidence=None,
                )
                for offset in (1, 2, 3)
            ],
            model_version="stub-v0",
            generated_at=datetime.now(UTC),
        )
