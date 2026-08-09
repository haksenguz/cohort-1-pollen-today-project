"""Slice A read types. Source of truth: schema/forecast.graphql.

Fields are snake_case here and camelCase in the SDL; Ariadne's
``snake_case_fallback_resolvers`` bridges the two, so nothing needs aliasing.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from pollen.libs.enums import PollenType, Region, RiskLevel


class ForecastDayDTO(BaseModel):
    date: str
    risk_level: RiskLevel
    #: 0-1. None for the persistence baseline, which does not produce one.
    confidence: float | None = None


class ForecastDTO(BaseModel):
    # Pydantic reserves the ``model_`` prefix; the SDL field is modelVersion and
    # renaming it would be a contract change, so relax the namespace instead.
    model_config = ConfigDict(protected_namespaces=())

    region: Region
    pollen_type: PollenType
    days: list[ForecastDayDTO]
    model_version: str
    generated_at: datetime
