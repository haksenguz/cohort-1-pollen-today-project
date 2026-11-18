"""Bring-your-own-LLM-key: provider allowlist, encryption, and lookup.

The base URL is never user input. A user picks a provider name and the server
maps it to a fixed URL, so a saved key cannot point the chat at an arbitrary
host (SSRF). Keys are stored as Fernet ciphertext and never logged or returned.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import get_settings
from app.models import UserLLMSetting

PROVIDER_BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

DEFAULT_MODELS: dict[str, str] = {
    "groq": "openai/gpt-oss-20b",
    "openai": "gpt-4o-mini",
    "openrouter": "openai/gpt-4o-mini",
}

MODEL_MAX_LENGTH = 128


@dataclass(frozen=True)
class UserLLMConfig:
    """What a chat turn needs to call the provider with the user's key.

    `api_key` is None when the stored ciphertext cannot be decrypted (the
    secret changed). The caller must then refuse rather than fall back.
    """

    api_key: str | None
    base_url: str
    model: str


def resolve_model(provider: str, model: str | None) -> str:
    chosen = (model or "").strip()
    return chosen or DEFAULT_MODELS[provider]


def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.llm_key_secret or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(token: str) -> str:
    """Raises `InvalidToken` when the ciphertext does not decrypt."""
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")


def key_hint(api_key: str) -> str:
    return api_key[-4:]


async def load_user_setting(session: AsyncSession, user_id: int) -> UserLLMSetting | None:
    result = await session.execute(select(UserLLMSetting).where(UserLLMSetting.user_id == user_id))
    return result.scalars().first()


def to_config(row: UserLLMSetting) -> UserLLMConfig:
    try:
        api_key: str | None = decrypt_api_key(row.api_key_encrypted)
    except InvalidToken:
        api_key = None
    return UserLLMConfig(
        api_key=api_key,
        base_url=PROVIDER_BASE_URLS[row.provider],
        model=row.model,
    )
