"""LLM client factory honoring OPENAI_BASE_URL and OPENAI_MODEL.

The default OpenAI client hard-codes the OpenAI endpoint. For an
OpenRouter-style proxy (or any other OpenAI-compatible API), the
caller sets OPENAI_BASE_URL and OPENAI_MODEL in `backend/.env`, and
this module threads them through to the SDK so the same chat code
hits either backend.

The `LLMClient` Protocol is structurally compatible with the one in
`app/agents/symptom_agent.py`, so the chat API can swap to
`get_openai_client_from_settings()` without changing the symptom
graph or any of its tests. The duplicated `OpenAIChatClient` in
symptom_agent is intentional for now — a follow-up PR collapses them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.core.config import get_settings


class ChatMessage(Protocol):
    role: str
    content: str


class LLMClient(Protocol):
    """The only boundary the chat code has with a model.

    A real implementation talks to OpenAI (or an OpenAI-compatible
    proxy via OPENAI_BASE_URL); tests supply a scripted fake.
    """

    def complete(self, messages: Sequence[ChatMessage]) -> str: ...


def _import_openai_sdk():
    """Lazy import so tests can monkeypatch without pulling openai."""
    import openai

    return openai.OpenAI


class OpenAIChatClient:
    """Thin wrapper around the OpenAI SDK satisfying `LLMClient`."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        OpenAI = _import_openai_sdk()
        self._client = OpenAI(**kwargs)
        self._model = model

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=0,
        )
        return response.choices[0].message.content or ""


def _build_openai_client(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
) -> OpenAIChatClient:
    return OpenAIChatClient(api_key=api_key, model=model, base_url=base_url)


def get_openai_client_from_settings() -> LLMClient:
    """Build an LLM client from the current Settings.

    Reads `openai_api_key`, `openai_base_url`, and `openai_model` from
    Settings (which pulls them from `backend/.env`). Raises a clear
    `RuntimeError` when the API key is missing — better than a 500
    on the first chat request.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "openai_api_key is not configured; set it in backend/.env before using the chat agent"
        )
    base_url = getattr(settings, "openai_base_url", "") or None
    model = getattr(settings, "openai_model", "") or "gpt-4o-mini"
    return _build_openai_client(
        api_key=settings.openai_api_key,
        base_url=base_url,
        model=model,
    )
