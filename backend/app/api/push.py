"""Web push subscriptions. The browser fetches the public VAPID key, subscribes
through the push manager, and posts the resulting endpoint and keys here."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field
from sqlmodel import delete, select

from app.core.config import get_settings
from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.models import PushSubscription

router = APIRouter(prefix="/api/push", tags=["push"])


class VapidKeyResponse(BaseModel):
    public_key: str | None


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class SubscribeRequest(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: SubscriptionKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(max_length=2048)


@router.get("/vapid-key")
async def vapid_key() -> VapidKeyResponse:
    return VapidKeyResponse(public_key=get_settings().vapid_public_key or None)


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    body: SubscribeRequest, current_user: CurrentUser, session: SessionDep
) -> Response:
    result = await session.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PushSubscription(user_id=current_user.id, endpoint=body.endpoint)
    row.user_id = current_user.id
    row.p256dh = body.keys.p256dh
    row.auth = body.keys.auth
    session.add(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: UnsubscribeRequest, current_user: CurrentUser, session: SessionDep
) -> Response:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.user_id == current_user.id,
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
