from __future__ import annotations

from pollen.components.analytics.dto import SeasonTimingDTO
from pollen.libs.enums import PollenType, Region


class AnalyticsService:
    """Slice B — Season Analytics. Owner: Giyos.

    STUB — blocked on historical data. The KMA API serves one day only
    ("최근 1일 간의 자료만 제공합니다"), so multi-year analysis needs a source
    we do not yet have. See OPEN_QUESTIONS.md §2.3.
    """

    def season_timing(self, region: Region, pollen_type: PollenType) -> SeasonTimingDTO:
        return SeasonTimingDTO(
            region=region,
            pollen_type=pollen_type,
            seasons=[],
            length_trend_days_per_year=None,
        )
