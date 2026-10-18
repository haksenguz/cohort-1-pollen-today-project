from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import CurrentUser, hash_password
from app.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    email: str
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


@router.get("/me")
async def read_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user, from_attributes=True)


@router.put("/me")
async def update_me(
    body: UserUpdateRequest, current_user: CurrentUser, session: SessionDep
) -> UserResponse:
    if body.email is not None and body.email != current_user.email:
        existing = await session.execute(select(User).where(User.email == body.email))
        if existing.scalars().first() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
        current_user.email = body.email

    if body.password is not None:
        current_user.password_hash = hash_password(body.password)

    # Tested against `model_fields_set`, not against `is not None`, because
    # `None` is a legitimate value here and not the same as "not mentioned".
    # With an `is not None` guard a location could be set but never cleared: a
    # user who saved the wrong place had no way back, and the chat's
    # `no_location` card - which tells someone to fix their location - offered
    # no matching way to undo it. Omitting the field still means "leave it".
    if "latitude" in body.model_fields_set:
        current_user.latitude = body.latitude
    if "longitude" in body.model_fields_set:
        current_user.longitude = body.longitude

    current_user.updated_at = datetime.now(UTC)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return UserResponse.model_validate(current_user, from_attributes=True)
