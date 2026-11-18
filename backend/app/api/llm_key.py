"""Bring-your-own-LLM-key settings, under /api/users/me/llm.

The key goes in on PUT and never comes back out. GET returns only the last four
characters as a hint.
"""

import logging

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field, field_validator

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.models import UserLLMSetting
from app.services.llm_key import (
    MODEL_MAX_LENGTH,
    PROVIDER_BASE_URLS,
    decrypt_api_key,
    encrypt_api_key,
    key_hint,
    load_user_setting,
    resolve_model,
)

router = APIRouter(prefix="/api/users/me/llm", tags=["users"])
logger = logging.getLogger(__name__)


class LLMKeyRequest(BaseModel):
    # A plain str with length limits, not an echoed value: the app's 422 handler
    # strips `input` from every validation error, so a rejected key is never
    # sent back. The max length stops a huge value from being stored or logged.
    api_key: str = Field(min_length=8, max_length=512)
    provider: str
    model: str | None = Field(default=None, max_length=MODEL_MAX_LENGTH)

    @field_validator("api_key")
    @classmethod
    def _strip_key(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 8:
            raise ValueError("API key is too short")
        return stripped

    @field_validator("provider")
    @classmethod
    def _provider_is_allowed(cls, value: str) -> str:
        if value not in PROVIDER_BASE_URLS:
            raise ValueError("provider must be one of: groq, openai, openrouter")
        return value

    @field_validator("model")
    @classmethod
    def _model_is_clean(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class LLMSettingResponse(BaseModel):
    configured: bool
    key_hint: str
    provider: str | None
    base_url: str | None
    model: str | None


def _response(row: UserLLMSetting | None) -> LLMSettingResponse:
    if row is None:
        return LLMSettingResponse(
            configured=False, key_hint="", provider=None, base_url=None, model=None
        )
    hint = ""
    try:
        hint = key_hint(decrypt_api_key(row.api_key_encrypted))
    except InvalidToken:
        # The secret changed since the key was saved. Say so without the key.
        logger.warning("stored LLM key for user %s cannot be decrypted", row.user_id)
    return LLMSettingResponse(
        configured=True,
        key_hint=hint,
        provider=row.provider,
        base_url=PROVIDER_BASE_URLS[row.provider],
        model=row.model,
    )


@router.get("")
async def read_llm_setting(current_user: CurrentUser, session: SessionDep) -> LLMSettingResponse:
    return _response(await load_user_setting(session, current_user.id))


@router.put("")
async def save_llm_setting(
    body: LLMKeyRequest, current_user: CurrentUser, session: SessionDep
) -> LLMSettingResponse:
    provider = body.provider
    model = resolve_model(provider, body.model)
    encrypted = encrypt_api_key(body.api_key)

    row = await load_user_setting(session, current_user.id)
    if row is None:
        row = UserLLMSetting(
            user_id=current_user.id,
            provider=provider,
            model=model,
            api_key_encrypted=encrypted,
        )
    else:
        row.provider = provider
        row.model = model
        row.api_key_encrypted = encrypted
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _response(row)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_setting(current_user: CurrentUser, session: SessionDep) -> Response:
    row = await load_user_setting(session, current_user.id)
    if row is not None:
        await session.delete(row)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
