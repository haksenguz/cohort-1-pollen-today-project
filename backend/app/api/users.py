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
    if body.latitude is not None:
        current_user.latitude = body.latitude
    if body.longitude is not None:
        current_user.longitude = body.longitude

    current_user.updated_at = datetime.now(UTC)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return UserResponse.model_validate(current_user, from_attributes=True)
