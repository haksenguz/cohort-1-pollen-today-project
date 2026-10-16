"""Tests for app/core/openai_client.py — the single boundary with a model.

The factory honors OPENAI_BASE_URL (so an OpenRouter-style proxy works),
OPENAI_MODEL, and the J6 cost/latency guard (max tokens + timeout). Provider
failures are normalized into `LLMCallError` with a stable `kind` so callers
never string-match SDK exception types (J4).

The LLMClient Protocol here is structurally compatible with the one in
symptom_agent so chat.py can swap to this factory without touching the agent.
"""

import pytest

from app.core.openai_client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    LLMCallError,
    OpenAIChatClient,
    _build_openai_client,
    _classify,
    function_tool_spec,
    get_openai_client_from_settings,
)


def _fake_sdk(monkeypatch, captured: dict, content: str = "hi"):
    """Install a fake OpenAI SDK that records the constructor kwargs and the
    completions.create kwargs, and returns `content` as the message body."""

    class FakeCompletions:
        def create(self, **kwargs):
            captured["create"] = kwargs

            class _Resp:
                choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]

            return _Resp()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)
    return FakeOpenAI


@pytest.fixture
def fake_settings(monkeypatch):
    """A helper that sets OPENAI_API_KEY to a sentinel and clears the rest."""

    def _set(
        *,
        api_key: str = "sk-test",
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ):
        monkeypatch.setenv("OPENAI_API_KEY", api_key)
        if base_url is None:
            monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        else:
            monkeypatch.setenv("OPENAI_BASE_URL", base_url)
        if model is None:
            monkeypatch.delenv("OPENAI_MODEL", raising=False)
        else:
            monkeypatch.setenv("OPENAI_MODEL", model)
        if max_tokens is None:
            monkeypatch.delenv("OPENAI_MAX_TOKENS", raising=False)
        else:
            monkeypatch.setenv("OPENAI_MAX_TOKENS", str(max_tokens))
        if timeout is None:
            monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
        else:
            monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", str(timeout))
        from app.core.config import get_settings

        get_settings.cache_clear()

    yield _set
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_build_client_honors_base_url_and_model(monkeypatch):
    """OPENAI_BASE_URL and OPENAI_MODEL flow through to the OpenAI SDK constructor."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

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
    _fake_sdk(monkeypatch, captured)

    _build_openai_client(api_key="sk-test", base_url=None, model="gpt-4o-mini")

    assert "base_url" not in captured  # OpenAI SDK default
    assert captured["api_key"] == "sk-test"


# ---------------------------------------------------------------------------
# J6: cost and latency guard.
# ---------------------------------------------------------------------------


def test_timeout_and_max_retries_are_passed_to_the_sdk(monkeypatch):
    """The latency budget is enforced on the SDK client, so it applies to
    every call this instance makes rather than being re-passed per request."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    _build_openai_client(api_key="sk-test", base_url=None, model="gpt-4o-mini", timeout=7.5)

    assert captured["timeout"] == 7.5
    assert captured["max_retries"] == 2


def test_default_timeout_is_bounded(monkeypatch):
    """A hung provider must not hang the SSE stream forever."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    _build_openai_client(api_key="sk-test", base_url=None, model="gpt-4o-mini")

    assert captured["timeout"] == DEFAULT_TIMEOUT_SECONDS
    assert 0 < DEFAULT_TIMEOUT_SECONDS <= 60


def test_max_tokens_is_sent_on_every_completion(monkeypatch):
    """One turn can never burn an unbounded number of output tokens."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    client = _build_openai_client(
        api_key="sk-test", base_url=None, model="gpt-4o-mini", max_tokens=256
    )
    client.complete([{"role": "user", "content": "hi"}])

    assert captured["create"]["max_tokens"] == 256
    assert DEFAULT_MAX_TOKENS > 0


def test_settings_can_override_the_guards(fake_settings, monkeypatch):
    """OPENAI_MAX_TOKENS / OPENAI_TIMEOUT_SECONDS reach the built client."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)
    fake_settings(api_key="sk-abc", max_tokens=128, timeout=3.0)

    get_openai_client_from_settings()

    assert captured["timeout"] == 3.0
    assert captured["max_retries"] == 2


def test_zero_guards_fall_back_to_defaults(fake_settings, monkeypatch):
    """The config defaults are 0/0.0 meaning 'unset', not 'no limit'."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)
    fake_settings(api_key="sk-abc", max_tokens=0, timeout=0.0)

    get_openai_client_from_settings()

    assert captured["timeout"] == DEFAULT_TIMEOUT_SECONDS


def test_openai_chat_client_calls_completions(monkeypatch):
    """OpenAIChatClient.complete builds the right chat.completions call."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")
    out = client.complete(
        [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert out == "hi"
    assert captured["create"]["model"] == "gpt-4o-mini"
    assert captured["create"]["temperature"] == 0


def test_complete_accepts_dict_messages(monkeypatch):
    """The real chat path: symptom_agent.ChatMessage is a TypedDict.

    This is the shape production actually sends. The client previously
    read `m.role`, which raised AttributeError on dicts and made every
    live chat turn fail extraction.
    """
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")
    out = client.complete(
        [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert out == "hi"
    assert captured["create"]["messages"] == [
        {"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "hello"},
    ]


def test_complete_does_not_mutate_caller_messages(monkeypatch):
    """The payload sent to the SDK is a copy, not the caller's objects."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    original = {"role": "user", "content": "hello"}
    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")
    client.complete([original])

    assert original == {"role": "user", "content": "hello"}


# ---------------------------------------------------------------------------
# J4: every provider failure becomes an LLMCallError with a stable `kind`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exc_name", "message", "expected"),
    [
        ("APITimeoutError", "Request timed out", "timeout"),
        ("RateLimitError", "429 Too Many Requests", "rate_limit"),
        ("APIConnectionError", "Connection reset by peer", "unavailable"),
        ("InternalServerError", "upstream boom", "unavailable"),
        ("AuthenticationError", "Incorrect API key provided", "unavailable"),
    ],
)
def test_sdk_failures_are_classified(monkeypatch, exc_name, message, expected):
    """Callers branch on `kind`; they never catch SDK exception types."""
    exc_type = type(exc_name, (Exception,), {})
    raised = exc_type(message)

    class FakeCompletions:
        def create(self, **kwargs):
            raise raised

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)
    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")

    with pytest.raises(LLMCallError) as excinfo:
        client.complete([{"role": "user", "content": "hi"}])

    assert excinfo.value.kind == expected
    # The SDK exception is chained for logs, never surfaced to the user.
    assert excinfo.value.__cause__ is raised


def test_unrecognized_exception_still_becomes_an_llm_call_error():
    """A brand-new SDK error must not escape as a raw exception."""
    err = _classify(ValueError("something entirely new"))

    assert isinstance(err, LLMCallError)
    assert err.kind == "unavailable"


def test_failure_detail_keeps_the_exception_class():
    """A rejected key, a wrong host, and a momentary network blip all collapse
    into `unavailable`, so the detail has to keep the exception class or the
    logs cannot tell them apart.
    """
    auth = _classify(type("AuthenticationError", (Exception,), {})("Incorrect API key provided"))
    conn = _classify(type("APIConnectionError", (Exception,), {})("Connection error."))

    assert auth.kind == conn.kind == "unavailable"
    assert "AuthenticationError" in auth.detail
    assert "APIConnectionError" in conn.detail
    assert auth.detail != conn.detail


def test_none_content_is_a_malformed_failure_not_an_empty_string(monkeypatch):
    """A 200 with no body is a failure, not an empty answer.

    Returning "" here would make the extraction node look like a silent
    model failure and, worse, could read as 'the model had nothing to say'
    rather than 'the provider is misbehaving'.
    """
    captured: dict = {}
    _fake_sdk(monkeypatch, captured, content=None)
    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini")

    with pytest.raises(LLMCallError) as excinfo:
        client.complete([{"role": "user", "content": "hi"}])

    assert excinfo.value.kind == "malformed"


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


# ---------------------------------------------------------------------------
# Optional tool calling.
#
# `complete` is still the whole required contract and still sends no tools;
# `complete_with_tools` is a separate capability so no existing fake or call
# site had to change to get it.
# ---------------------------------------------------------------------------


def _fake_sdk_with_tool_calls(monkeypatch, captured: dict, content, tool_calls):
    class FakeCompletions:
        def create(self, **kwargs):
            captured["create"] = kwargs
            message = type("M", (), {"content": content, "tool_calls": tool_calls})()
            return type("R", (), {"choices": [type("C", (), {"message": message})()]})()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)


def _tool_call_stub(call_id="call_1", name="lookup_clinic", arguments='{"latitude": 37.5}'):
    function = type("F", (), {"name": name, "arguments": arguments})()
    return type("TC", (), {"id": call_id, "function": function})()


def test_complete_still_sends_no_tools(monkeypatch):
    """The regression that matters: adding tools must not touch `complete`."""
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)

    OpenAIChatClient(api_key="sk-test").complete([{"role": "user", "content": "hi"}])

    assert "tools" not in captured["create"]
    assert "tool_choice" not in captured["create"]


def test_complete_with_tools_sends_the_offered_schemas(monkeypatch):
    captured: dict = {}
    _fake_sdk_with_tool_calls(monkeypatch, captured, content="no lookup needed", tool_calls=None)
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    turn = OpenAIChatClient(api_key="sk-test").complete_with_tools(
        [{"role": "user", "content": "clinic near me?"}], [spec]
    )

    assert captured["create"]["tools"] == [spec]
    assert "tool_choice" not in captured["create"], "no model may be forced to call a tool"
    assert turn.content == "no lookup needed"
    assert turn.tool_calls == ()


def test_complete_with_tools_normalizes_a_tool_call(monkeypatch):
    captured: dict = {}
    _fake_sdk_with_tool_calls(
        monkeypatch,
        captured,
        content=None,
        tool_calls=[_tool_call_stub(arguments='{"latitude": 37.5}')],
    )
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    turn = OpenAIChatClient(api_key="sk-test").complete_with_tools(
        [{"role": "user", "content": "clinic near me?"}], [spec]
    )

    assert len(turn.tool_calls) == 1
    call = turn.tool_calls[0]
    assert call.id == "call_1"
    assert call.name == "lookup_clinic"
    assert call.arguments == {"latitude": 37.5}
    assert turn.content is None


@pytest.mark.parametrize("raw", ["{not json", "", "   ", "[1, 2]", None])
def test_unparseable_tool_arguments_degrade_to_empty(monkeypatch, raw):
    """A model that emitted broken JSON has not earned a crashed turn."""
    captured: dict = {}
    _fake_sdk_with_tool_calls(
        monkeypatch, captured, content=None, tool_calls=[_tool_call_stub(arguments=raw)]
    )
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    turn = OpenAIChatClient(api_key="sk-test").complete_with_tools(
        [{"role": "user", "content": "clinic?"}], [spec]
    )

    assert turn.tool_calls[0].arguments == {}


def test_none_content_with_no_tool_call_is_malformed(monkeypatch):
    """Same rule as `complete`: silence is a failure, not an empty answer."""
    captured: dict = {}
    _fake_sdk_with_tool_calls(monkeypatch, captured, content=None, tool_calls=[])
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    with pytest.raises(LLMCallError) as excinfo:
        OpenAIChatClient(api_key="sk-test").complete_with_tools(
            [{"role": "user", "content": "hi"}], [spec]
        )

    assert excinfo.value.kind == "malformed"


def test_tool_enabled_calls_are_classified_like_any_other(monkeypatch):
    raised = type("RateLimitError", (Exception,), {})("429")

    class FakeCompletions:
        def create(self, **kwargs):
            raise raised

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.core.openai_client._import_openai_sdk", lambda: FakeOpenAI)
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    with pytest.raises(LLMCallError) as excinfo:
        OpenAIChatClient(api_key="sk-test").complete_with_tools(
            [{"role": "user", "content": "hi"}], [spec]
        )

    assert excinfo.value.kind == "rate_limit"


def test_tool_result_messages_carry_their_tool_call_id(monkeypatch):
    """A tool observation is a `role: tool` turn that must name its call."""
    captured: dict = {}
    _fake_sdk_with_tool_calls(monkeypatch, captured, content="done", tool_calls=None)
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    OpenAIChatClient(api_key="sk-test").complete_with_tools(
        [
            {"role": "user", "content": "clinic?"},
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "lookup_clinic",
                "content": '{"name": "Some Clinic"}',
            },
        ],
        [spec],
    )

    assert captured["create"]["messages"][1] == {
        "role": "tool",
        "content": '{"name": "Some Clinic"}',
        "tool_call_id": "call_1",
        "name": "lookup_clinic",
    }


def test_ordinary_messages_are_still_exactly_role_and_content(monkeypatch):
    """The optional payload keys must not leak into an ordinary turn."""
    captured: dict = {}
    _fake_sdk_with_tool_calls(monkeypatch, captured, content="done", tool_calls=None)
    spec = function_tool_spec("lookup_clinic", "Look up a clinic.", {"type": "object"})

    OpenAIChatClient(api_key="sk-test").complete_with_tools(
        [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}], [spec]
    )

    assert captured["create"]["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]


def test_the_real_client_satisfies_both_protocols(monkeypatch):
    """`ToolCallingLLMClient` extends `LLMClient`; it never replaces it."""
    _fake_sdk(monkeypatch, {})
    client = OpenAIChatClient(api_key="sk-test", model="gpt-4o-mini", base_url=None)

    assert callable(client.complete)
    assert callable(client.complete_with_tools)
