"""Local-dev only: let the running server accept an LLM credential from the UI.

Why this exists
---------------
The chat agent reads `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` from
`backend/.env` at import time. During local development that means: edit the
file, restart the API, repeat. The person testing the app has to leave the
browser to change a setting they can only verify from the browser.

This router writes the same `.env` keys and busts the settings cache so the
next chat turn uses them, no restart.

Safety
------
This is a credential-write endpoint, so it is off unless explicitly enabled:

- `dev_settings_enabled` defaults to **False**. It is flipped on only in a
  local `.env`, which is gitignored and never shipped.
- The response never echoes the key back — only whether one is set, plus a
  last-4 hint. A `GET` on this endpoint must never be the way a secret leaks.
- The key is written to a gitignored file and is never logged.
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev", tags=["dev"])

# Keys this endpoint is allowed to touch. Anything else in .env is left alone.
_WRITABLE = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")
_ENV_FILE = Path(".env")


class LlmSettingsIn(BaseModel):
    # max_length matters here for a non-obvious reason: FastAPI validates the
    # body BEFORE the endpoint runs, so an over-long api_key produces a 422
    # whose `input` field echoes the submitted secret back to the client. That
    # bypasses the 404 guard entirely. The bounds are now also enforced
    # explicitly in the handler, and `_reject_injection` strips anything that
    # could forge a second .env line.
    api_key: str = Field(default="", max_length=512)
    base_url: str = Field(default="", max_length=512)
    model: str = Field(default="", max_length=128)


class LlmSettingsOut(BaseModel):
    """Never contains the key itself — only whether one is present."""

    configured: bool
    key_hint: str
    base_url: str
    model: str


def _require_enabled() -> None:
    if not get_settings().dev_settings_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _hint(api_key: str) -> str:
    """Last 4 characters only, so the UI can confirm *which* key is loaded
    without the response ever carrying the secret."""
    return f"...{api_key[-4:]}" if len(api_key) >= 4 else ""


def _upsert_env(values: dict[str, str]) -> None:
    """Rewrite only the lines we own; every other line is preserved verbatim.

    Appends a missing key rather than rewriting the file, so a `.env` that has
    never held an LLM key still works.
    """
    path = _ENV_FILE
    if not path.is_file():
        path.write_text("", encoding="utf-8")

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    seen: set[str] = set()

    for index, line in enumerate(lines):
        match = re.match(r"^([A-Z_]+)=", line)
        if match and match.group(1) in values:
            key = match.group(1)
            lines[index] = f"{key}={values[key]}"
            seen.add(key)

    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.get("/llm", response_model=LlmSettingsOut)
async def read_llm_settings() -> LlmSettingsOut:
    _require_enabled()
    settings = get_settings()
    return LlmSettingsOut(
        configured=bool(settings.openai_api_key),
        key_hint=_hint(settings.openai_api_key),
        base_url=settings.openai_base_url,
        model=settings.openai_model,
    )


def _reject_injection(value: str, field: str) -> str:
    """Strip and reject anything that could forge a second `.env` line.

    `_upsert_env` writes `KEY={value}` into a line-oriented file, so a value
    containing a newline would let a caller append arbitrary config — including
    `DEV_SETTINGS_ENABLED=true` on a server where it is off, or a replacement
    `DATABASE_URL`. Keys and URLs never contain control characters, so rejecting
    them outright costs nothing real.
    """
    cleaned = value.strip()
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in cleaned):
        raise HTTPException(
            status_code=422,
            detail=f"{field} must not contain control characters",
        )
    return cleaned


@router.put("/llm", response_model=LlmSettingsOut)
async def write_llm_settings(payload: LlmSettingsIn) -> LlmSettingsOut:
    _require_enabled()

    # An empty field means "leave it alone", not "clear it". Without this, a
    # save that carries only a key silently blanks a base URL and model that
    # were working, and the app stops talking to the provider with no obvious
    # cause. Clearing a field is an explicit action, done by editing .env.
    settings = get_settings()
    current = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "OPENAI_BASE_URL": settings.openai_base_url,
        "OPENAI_MODEL": settings.openai_model,
    }
    submitted = {
        "OPENAI_API_KEY": _reject_injection(payload.api_key, "api_key"),
        "OPENAI_BASE_URL": _reject_injection(payload.base_url, "base_url"),
        "OPENAI_MODEL": _reject_injection(payload.model, "model"),
    }
    to_write = {key: value for key, value in submitted.items() if value.strip() or not current[key]}

    _upsert_env(to_write)

    # The settings object is lru_cached for the process, and the chat client
    # memoises the built OpenAI client, so both must be rebuilt before the next
    # message — otherwise the app keeps calling the old (possibly empty) key
    # until someone restarts the API, which is the exact problem this endpoint
    # exists to remove.
    get_settings.cache_clear()
    from app.api.chat import _LazyLLMClient

    _LazyLLMClient.reset_cached_clients()

    logger.info(
        "dev settings updated (model=%s, key=%s)",
        to_write.get("OPENAI_MODEL", "<unchanged>"),
        "set" if to_write.get("OPENAI_API_KEY") else "unchanged",
    )

    return await read_llm_settings()
