"""Slice B read types. Source of truth: schema/analytics.graphql."""

from __future__ import annotations

from pydantic import BaseModel

from pollen.libs.enums import PollenType, Region


class SeasonWindowDTO(BaseModel):
    year: int
    region: Region
    pollen_type: PollenType
    start_date: str
    end_date: str
    length_days: int


class SeasonTimingDTO(BaseModel):
    region: Region
    pollen_type: PollenType
    seasons: list[SeasonWindowDTO]
    #: Days per year. Positive means the season is lengthening.
    length_trend_days_per_year: float | None = None
