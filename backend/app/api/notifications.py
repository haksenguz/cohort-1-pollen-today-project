"""Read alerts and manage notification preferences. Alert *generation* lives
in `app/services/notification_service.py`; this router only reads/writes.
Follows the auth pattern in `app/api/allergies.py` — every route is scoped to
`CurrentUser`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.enums import RiskLevel
from app.core.security import CurrentUser
from app.models import Alert
from app.services.notification_service import get_or_create_preferences

router = APIRouter(tags=["notifications"])


class AlertResponse(BaseModel):
    id: int
    risk_level: str
    alert_type: str
    message: str
    is_read: bool
    created_at: datetime


class PreferenceResponse(BaseModel):
    alert_pollen: bool
    alert_air_quality: bool
    alert_weather: bool
    min_risk_level: str
    quiet_hours_start: int | None
    quiet_hours_end: int | None


Hour = Annotated[int, Field(ge=0, le=23)]


class PreferenceUpdateRequest(BaseModel):
    alert_pollen: bool | None = None
    alert_air_quality: bool | None = None
    alert_weather: bool | None = None
    min_risk_level: RiskLevel | None = None
    quiet_hours_start: Hour | None = None
    quiet_hours_end: Hour | None = None


@router.get("/api/alerts")
async def list_alerts(
    current_user: CurrentUser,
    session: SessionDep,
    unread_only: bool = Query(default=False),
) -> list[AlertResponse]:
    query = select(Alert).where(Alert.user_id == current_user.id)
    if unread_only:
        query = query.where(Alert.is_read.is_(False))
    query = query.order_by(Alert.created_at.desc())
    result = await session.execute(query)
    return [
        AlertResponse.model_validate(row, from_attributes=True) for row in result.scalars().all()
    ]


@router.patch("/api/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: int, current_user: CurrentUser, session: SessionDep
) -> AlertResponse:
    alert = await session.get(Alert, alert_id)
    if alert is None or alert.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert.is_read = True
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return AlertResponse.model_validate(alert, from_attributes=True)


@router.get("/api/notifications/preferences")
async def read_preferences(current_user: CurrentUser, session: SessionDep) -> PreferenceResponse:
    pref = await get_or_create_preferences(session, current_user.id)
    return PreferenceResponse.model_validate(pref, from_attributes=True)


@router.put("/api/notifications/preferences")
async def update_preferences(
    body: PreferenceUpdateRequest, current_user: CurrentUser, session: SessionDep
) -> PreferenceResponse:
    pref = await get_or_create_preferences(session, current_user.id)
    updates = body.model_dump(exclude_unset=True)
    if "min_risk_level" in updates and updates["min_risk_level"] is not None:
        updates["min_risk_level"] = RiskLevel(updates["min_risk_level"]).value
    for field, value in updates.items():
        setattr(pref, field, value)
    session.add(pref)
    await session.commit()
    await session.refresh(pref)
    return PreferenceResponse.model_validate(pref, from_attributes=True)
