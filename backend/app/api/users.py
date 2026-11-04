from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
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


# A phone number as a person writes it: digits, spaces, dashes, brackets and an
# optional leading +. Rejecting anything else keeps a typo out of the one
# field that has to work when someone cannot breathe.
_PHONE_ALLOWED = set("0123456789+-() .")
_PHONE_MIN_DIGITS = 7
_PHONE_MAX_DIGITS = 15


class EmergencyContactRequest(BaseModel):
    """One emergency contact. Every field is optional, and empty clears it."""

    name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=200)

    @field_validator("phone")
    @classmethod
    def _phone_is_callable(cls, value: str | None) -> str | None:
        if value is None:
            return None
        phone = value.strip()
        if phone == "":
            return None
        if any(character not in _PHONE_ALLOWED for character in phone):
            raise ValueError(
                "Use a phone number only: digits, spaces, dashes, brackets and a "
                "leading + are fine. Letters are not."
            )
        digits = [character for character in phone if character.isdigit()]
        if not _PHONE_MIN_DIGITS <= len(digits) <= _PHONE_MAX_DIGITS:
            raise ValueError(
                f"A phone number needs {_PHONE_MIN_DIGITS} to {_PHONE_MAX_DIGITS} digits. "
                "Include the country code if the number is not local."
            )
        return phone


class EmergencyContactResponse(BaseModel):
    name: str | None
    phone: str | None
    note: str | None


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


def _emergency_contact(user: User) -> EmergencyContactResponse:
    return EmergencyContactResponse(
        name=user.emergency_contact_name,
        phone=user.emergency_contact_phone,
        note=user.emergency_contact_note,
    )


@router.get("/me/emergency-contact")
async def read_emergency_contact(current_user: CurrentUser) -> EmergencyContactResponse:
    """The contact the user chose. Empty until they save one."""
    return _emergency_contact(current_user)


@router.put("/me/emergency-contact")
async def save_emergency_contact(
    body: EmergencyContactRequest, current_user: CurrentUser, session: SessionDep
) -> EmergencyContactResponse:
    """Save or clear the emergency contact.

    An empty value clears the field, so there is one write path for both
    saving and clearing. The app cannot call this number: it is a number the
    person chooses to dial.
    """
    current_user.emergency_contact_name = (body.name or "").strip() or None
    current_user.emergency_contact_phone = body.phone
    current_user.emergency_contact_note = (body.note or "").strip() or None
    current_user.updated_at = datetime.now(UTC)

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return _emergency_contact(current_user)
