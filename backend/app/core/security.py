"""Password hashing, JWT issuance, and the current-user dependency.

The rule engine (`app/services/triage.py`) still owns every safety decision.
Nothing here makes clinical judgments; it only proves who is asking.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionDep
from app.models import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h

_password_hash = PasswordHash((BcryptHasher(),))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _get_or_create_demo_user(session: AsyncSession) -> User:
    """ADR 0003: idempotent seed for the demo user. The password hash is
    a placeholder that can never match a real login attempt — there is no
    password login for this account; it exists purely so a request with
    no bearer token, when DEMO_MODE is on, resolves to a known user."""
    from sqlalchemy import select

    settings = get_settings()
    existing = await session.execute(select(User).where(User.email == settings.demo_user_email))
    user = existing.scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=settings.demo_user_email,
        password_hash="!demo-no-login",  # noqa: S106
        latitude=37.5665,
        longitude=126.978,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_current_user(
    session: SessionDep,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    # ADR 0003: demo-mode fallback. When DEMO_MODE is on and the request
    # has no token, resolve to the seeded demo user instead of 401'ing.
    # Off (the default), this branch is dead code and behaviour is
    # unchanged.
    if token is None and get_settings().demo_mode:
        return await _get_or_create_demo_user(session)

    if token is None:
        raise _credentials_error()
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise _credentials_error() from exc
    raw_user_id = payload.get("sub")
    if raw_user_id is None:
        raise _credentials_error()
    try:
        user = await session.get(User, int(raw_user_id))
    except (TypeError, ValueError) as exc:
        raise _credentials_error() from exc
    if user is None:
        raise _credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
