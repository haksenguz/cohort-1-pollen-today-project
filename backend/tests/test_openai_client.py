"""Tests for app/core/openai_client.py.

The factory honors OPENAI_BASE_URL (so an OpenRouter-style proxy works)
and OPENAI_MODEL, and raises a clear error when the API key is missing.
The LLMClient Protocol is structurally compatible with the one in
symptom_agent so chat.py can swap to this factory without touching
the agent.
"""

import pytest

from app.core.openai_client import (
    OpenAIChatClient,
    _build_openai_client,
    get_openai_client_from_settings,
)


@pytest.fixture
def fake_settings(monkeypatch):
    """A helper that sets OPENAI_API_KEY to a sentinel and clears the rest."""

    def _set(*, api_key: str = "sk-test", base_url: str | None = None, model: str | None = None):
        monkeypatch.setenv("OPENAI_API_KEY", api_key)
        if base_url is None:
            monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        else:
            monkeypatch.setenv("OPENAI_BASE_URL", base_url)
        if model is None:
            monkeypatch.delenv("OPENAI_MODEL", raising=False)
        else:
            monkeypatch.setenv("OPENAI_MODEL", model)
        from app.core.config import get_settings

        get_settings.cache_clear()

    return _set


def test_build_client_honors_base_url_and_model(monkeypatch):
    """OPENAI_BASE_URL and OPENAI_MODEL flow through to the OpenAI SDK constructor."""
    captured: dict = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)

    client = _build_openai_client(
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
    )

    assert captured["api_key"] == "sk-test"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert isinstance(client, OpenAIChatClient)
    assert client._model == "openai/gpt-4o-mini"


def test_build_client_defaults_to_openai_when_no_base_url(monkeypatch):
    """No OPENAI_BASE_URL means we hit OpenAI's default endpoint."""
    captured: dict = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)

    _build_openai_client(api_key="sk-test", base_url=None, model="gpt-4o-mini")

    assert "base_url" not in captured  # OpenAI SDK default
    assert captured["api_key"] == "sk-test"


def test_openai_chat_client_calls_completions(monkeypatch):
    """OpenAIChatClient.complete builds the right chat.completions call."""

    class FakeCompletions:
        def create(self, **kwargs):
            class _Resp:
                choices = [type("C", (), {"message": type("M", (), {"content": "hi"})()})()]

            return _Resp()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)

    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")
    out = client.complete(
        [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert out == "hi"


def test_complete_accepts_dict_messages(monkeypatch):
    """The real chat path: symptom_agent.ChatMessage is a TypedDict.

    This is the shape production actually sends. The client previously
    read `m.role`, which raised AttributeError on dicts and made every
    live chat turn fail extraction.
    """
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class _Resp:
                choices = [type("C", (), {"message": type("M", (), {"content": "hi"})()})()]

            return _Resp()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)

    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")
    out = client.complete(
        [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert out == "hi"
    assert captured["messages"] == [
        {"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "hello"},
    ]


def test_complete_does_not_mutate_caller_messages(monkeypatch):
    """The payload sent to the SDK is a copy, not the caller's objects."""

    class FakeCompletions:
        def create(self, **kwargs):
            class _Resp:
                choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

            return _Resp()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)

    original = {"role": "user", "content": "hello"}
    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")
    client.complete([original])

    assert original == {"role": "user", "content": "hello"}


def test_get_client_from_settings_reads_all_three(fake_settings):
    fake_settings(
        api_key="sk-abc",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
    )
    client = get_openai_client_from_settings()
    # LLMClient is a Protocol — isinstance checks need @runtime_checkable,
    # so assert structural conformance instead.
    assert hasattr(client, "complete") and callable(client.complete)
    assert client._model == "openai/gpt-4o-mini"  # type: ignore[attr-defined]


def test_get_client_raises_when_api_key_missing(fake_settings):
    fake_settings(api_key="")
    with pytest.raises(RuntimeError, match="openai_api_key is not configured"):
        get_openai_client_from_settings()
