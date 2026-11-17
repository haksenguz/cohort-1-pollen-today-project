from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.rate_limit import get_auth_limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _enforce_auth_limit(request: Request) -> None:
    """Raise 429 when this client IP is over its auth budget."""
    client = request.client.host if request.client else "unknown"
    decision = await get_auth_limiter().check(client)
    if not decision.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Try again shortly.",
            headers=decision.headers,
        )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: Request, body: RegisterRequest, session: SessionDep) -> TokenResponse:
    await _enforce_auth_limit(request)
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalars().first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        latitude=body.latitude,
        longitude=body.longitude,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login")
async def login(request: Request, body: LoginRequest, session: SessionDep) -> TokenResponse:
    await _enforce_auth_limit(request)
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))
