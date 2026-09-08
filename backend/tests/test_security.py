import jwt
import pytest

from app.core.config import get_settings
from app.core.security import ALGORITHM, create_access_token, hash_password, verify_password


def test_hash_password_roundtrip():
    hashed = hash_password("correcthorse123")
    assert hashed != "correcthorse123"
    assert verify_password("correcthorse123", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correcthorse123")
    assert not verify_password("wrongpassword", hashed)


def test_create_access_token_encodes_subject():
    token = create_access_token(user_id=42)
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    assert payload["sub"] == "42"


def test_expired_token_is_rejected():
    settings = get_settings()
    import datetime as dt

    now = dt.datetime.now(dt.UTC)
    expired = jwt.encode(
        {"sub": "1", "iat": now - dt.timedelta(hours=2), "exp": now - dt.timedelta(hours=1)},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(expired, settings.jwt_secret, algorithms=[ALGORITHM])
