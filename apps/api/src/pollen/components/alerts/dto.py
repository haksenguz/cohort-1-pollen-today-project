"""Slice C read types. Source of truth: schema/alerts.graphql."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from pollen.libs.enums import PollenType, Region, RiskLevel


class AlertDTO(BaseModel):
    id: str
    region: Region
    pollen_type: PollenType
    #: The day the alert is about, not the day it was sent.
    target_date: str
    risk_level: RiskLevel
    channel: str
    sent_at: datetime
    message_text: str


class PaginatedAlertDTO(BaseModel):
    items: list[AlertDTO]
    total: int
    has_more: bool


class NewAlert(BaseModel):
    """What the alert job hands the service. Mongo assigns the id."""

    region: Region
    pollen_type: PollenType
    target_date: str
    risk_level: RiskLevel
    channel: str
    sent_at: datetime
    message_text: str
