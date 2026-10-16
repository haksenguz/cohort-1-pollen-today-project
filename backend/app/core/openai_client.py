"""The single boundary between the app and a language model (J7).

There is exactly one `OpenAIChatClient` in this codebase and it lives here.
`app.agents.symptom_agent` defines a *structural* `LLMClient` Protocol that this
class satisfies, so the symptom graph never imports a concrete client and its
offline tests keep using a scripted fake. `app.api.chat` builds the real client
through `get_openai_client_from_settings()`.

This module also owns the cost and latency guard (J6) and the failure
vocabulary (J4):

* `max_tokens` caps every completion so one turn can never burn an unbounded
  number of output tokens.
* `timeout` is a hard per-call ceiling so a hung provider can't hang the SSE
  stream. The OpenAI SDK retries transient errors twice by default; we keep
  that but let the timeout bound the whole thing.
* Every provider failure is translated into a `LLMCallError` carrying a
  `kind` — `timeout`, `rate_limit`, `unavailable`, or `malformed` — so callers
  decide how to degrade without string-matching SDK exception types.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# J6: a follow-up question or a JSON extraction is a few hundred tokens at
# most. 512 leaves generous headroom for a verbose JSON object while putting a
# hard ceiling on a single call's cost.
DEFAULT_MAX_TOKENS = 512

# J6: per-call latency budget. A streaming chat turn that takes longer than
# this is already a failed turn from the user's point of view.
DEFAULT_TIMEOUT_SECONDS = 20.0

LLMErrorKind = Literal["timeout", "rate_limit", "unavailable", "malformed"]


class LLMCallError(Exception):
    """A model call failed in a way the caller is expected to handle.

    `kind` is the stable contract: callers branch on it instead of catching
    specific SDK exceptions. `detail` is safe to log but never surfaced to a
    user verbatim.
    """

    def __init__(self, kind: LLMErrorKind, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


class ChatMessageLike(Protocol):
    """A chat turn as a plain mapping.

    `symptom_agent.ChatMessage` is a TypedDict, so every turn the agent builds
    is a dict at runtime, not an object with attributes. This module is handed
    those dicts directly, so the type here is a Mapping rather than an
    attribute Protocol.
    """

    def __getitem__(self, key: str) -> str: ...


class LLMClient(Protocol):
    """The only boundary the chat code has with a model.

    A real implementation talks to OpenAI (or an OpenAI-compatible proxy via
    OPENAI_BASE_URL); tests supply a scripted fake.

    `complete` is the whole contract. Tool calling is an *optional* extra
    capability with its own protocol (`ToolCallingLLMClient`) so a client that
    has never heard of tools still satisfies `LLMClient` unchanged.
    """

    def complete(self, messages: Sequence[ChatMessageLike]) -> str: ...


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation the model asked for.

    `arguments` is the provider's JSON argument object, parsed defensively: a
    malformed body yields `{}` rather than raising, because a model that
    emitted broken JSON has not earned a crashed turn.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolTurn:
    """What one tool-enabled model call returned.

    `content` is None on a turn that is purely a tool request. `tool_calls` is
    empty on an ordinary answer — the caller decides whether a step is a "reason"
    (answer) or an "act" (tool request), not this object.
    """

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


# An OpenAI-shaped function-tool declaration, built by the registry.
ToolSpec = dict[str, Any]


class ToolCallingLLMClient(Protocol):
    """OPTIONAL capability: a client that can be offered tools.

    Deliberately separate from `LLMClient`. Callers duck-type for
    `complete_with_tools` and fall back to the plain path when it is absent, so
    adding tool calling did not widen the one method every existing fake and
    every existing call site has to satisfy.
    """

    def complete_with_tools(
        self, messages: Sequence[ChatMessageLike], tools: Sequence[ToolSpec]
    ) -> ToolTurn: ...


def function_tool_spec(name: str, description: str, parameters: Mapping[str, Any]) -> ToolSpec:
    """Build one OpenAI `tools` entry from a JSON-schema parameter block."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": dict(parameters),
        },
    }


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Provider arguments arrive as a JSON string; parse or degrade to {}."""
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("openai_client: tool arguments were not valid JSON")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _message_payload(message: ChatMessageLike) -> dict[str, Any]:
    """Rebuild one turn as a plain dict for the SDK.

    `tool_call_id` / `name` are carried only when the caller supplied them, i.e.
    for a tool-result message. An ordinary turn stays exactly role + content.
    """
    payload: dict[str, Any] = {"role": message["role"], "content": message["content"]}
    for key in ("tool_call_id", "name"):
        if key in message:
            payload[key] = message[key]
    return payload


def _import_openai_sdk():
    """Lazy import so tests can monkeypatch without pulling openai."""
    import openai

    return openai.OpenAI


def _detail(exc: Exception, message: str) -> str:
    """Log-safe detail that keeps the exception class visible.

    Several distinct failures collapse into the single `unavailable` kind —
    a rejected key, a wrong host, and a momentary network blip are all
    `unavailable`. Without the class name in the log line they are
    indistinguishable, and a transient blip gets diagnosed as a credential
    problem (or the reverse) for no reason.
    """
    return f"{message} [{type(exc).__name__}]: {exc}"


def _classify(exc: Exception) -> LLMCallError:
    """Map an OpenAI SDK / transport exception onto our failure vocabulary.

    Matching is on exception *type name* rather than importing the SDK's error
    classes, so this stays correct across SDK versions and works for the
    OpenAI-compatible proxies that reuse the same class names.
    """
    name = type(exc).__name__
    text = str(exc).lower()

    if name in ("APITimeoutError", "Timeout", "ReadTimeout", "ConnectTimeout"):
        return LLMCallError("timeout", _detail(exc, "model call timed out"))
    if name == "RateLimitError" or "rate limit" in text or "429" in text:
        return LLMCallError("rate_limit", _detail(exc, "model rate limited"))
    if name in ("APIConnectionError", "APIError", "InternalServerError", "ServiceUnavailable"):
        return LLMCallError("unavailable", _detail(exc, "model unavailable"))
    if name == "AuthenticationError" or "unauthorized" in text or "invalid api key" in text:
        return LLMCallError("unavailable", _detail(exc, "model rejected the request"))
    return LLMCallError("unavailable", _detail(exc, "model call failed"))


class OpenAIChatClient:
    """Thin wrapper around the OpenAI SDK satisfying `LLMClient`.

    J6: `max_tokens` and `timeout` are enforced on the SDK client itself, so
    they apply to every call this instance makes. Provider failures are raised
    as `LLMCallError`; the raw SDK exception is never allowed to escape.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        kwargs: dict = {"api_key": api_key, "timeout": timeout, "max_retries": 2}
        if base_url:
            kwargs["base_url"] = base_url
        OpenAI = _import_openai_sdk()
        self._client = OpenAI(**kwargs)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, messages: Sequence[ChatMessageLike]) -> str:
        content = self._create(messages).choices[0].message.content
        # A 200 with an empty body (some proxies do this on overload) is a
        # failure, not an empty answer — the agent must treat it as one.
        if content is None:
            raise LLMCallError("malformed", "model returned no content")
        return content

    def complete_with_tools(
        self, messages: Sequence[ChatMessageLike], tools: Sequence[ToolSpec]
    ) -> ToolTurn:
        """Offer `tools` and return either an answer or a set of tool calls.

        Never sends `tool_choice`, so a provider that dislikes the parameter is
        never handed it, and no model is *forced* to call anything.
        """
        message = self._create(messages, tools=tools).choices[0].message
        raw_calls = getattr(message, "tool_calls", None) or []
        tool_calls = tuple(
            ToolCall(
                id=getattr(call, "id", "") or "",
                name=getattr(getattr(call, "function", None), "name", "") or "",
                arguments=_parse_arguments(
                    getattr(getattr(call, "function", None), "arguments", None)
                ),
            )
            for call in raw_calls
        )
        content = message.content
        if content is None and not tool_calls:
            raise LLMCallError("malformed", "model returned no content")
        return ToolTurn(content=content, tool_calls=tool_calls)

    def _create(self, messages: Sequence[ChatMessageLike], tools: Sequence[ToolSpec] | None = None):
        # Rebuild each turn as a fresh dict. `symptom_agent` passes TypedDicts,
        # so touching `m.role` here would raise AttributeError on the real chat
        # path. Copying also stops a caller mutating our payload after the call.
        payload = [_message_payload(m) for m in messages]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": payload,
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        if tools:
            kwargs["tools"] = list(tools)
        try:
            return self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 — normalized immediately below
            err = _classify(exc)
            logger.warning("openai_client: %s", err.detail)
            raise err from exc


def _build_openai_client(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> OpenAIChatClient:
    return OpenAIChatClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def get_openai_client_from_settings() -> LLMClient:
    """Build an LLM client from the current Settings.

    Reads `openai_api_key`, `openai_base_url`, and `openai_model` from Settings
    (which pulls them from `backend/.env`). J6: `openai_max_tokens` and
    `openai_timeout_seconds` cap cost and latency. Raises a clear `RuntimeError`
    when the API key is missing — better than a 500 on the first chat request.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "openai_api_key is not configured; set it in backend/.env before using the chat agent"
        )
    base_url = getattr(settings, "openai_base_url", "") or None
    model = getattr(settings, "openai_model", "") or "gpt-4o-mini"
    max_tokens = getattr(settings, "openai_max_tokens", 0) or DEFAULT_MAX_TOKENS
    timeout = getattr(settings, "openai_timeout_seconds", 0.0) or DEFAULT_TIMEOUT_SECONDS
    return _build_openai_client(
        api_key=settings.openai_api_key,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        timeout=timeout,
    )
