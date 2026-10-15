"""The dev LLM-settings endpoint is a credential-write route, so its guard is
the thing under test, not the happy path.

`dev_settings_enabled` defaults to False. If that ever flips by accident, a
deployed instance would accept an anonymous write of its own LLM credential.
These tests pin the dark default and pin that a response can never carry the
key back to the browser.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import dev_settings
from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    """TestClient pointed at a throwaway .env.

    The PUT handler writes to `_ENV_FILE`, which is a module-level `Path(".env")`
    relative to the process CWD — i.e. the developer's real config. Without
    this patch a passing test run silently replaces the operator's API key with
    the fixture's fake one. That is not a hypothetical: it happened, and the
    next chat request then used `https://example.invalid`.
    """
    env = tmp_path / ".env"
    env.write_text("JWT_SECRET=untouched\n", encoding="utf-8")
    monkeypatch.setattr(dev_settings, "_ENV_FILE", env)

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the flag on for the settings object the request will read.

    Set through the environment rather than by patching the cached Settings
    instance: the PUT handler calls `get_settings.cache_clear()`, which throws
    that instance away and rebuilds from env + .env, so a patched attribute
    would be silently dropped. Going through the env also means the result no
    longer depends on whether the developer running the suite has
    DEV_SETTINGS_ENABLED in their local .env — which is exactly why this test
    passed locally and 404'd in CI.
    """
    monkeypatch.setenv("DEV_SETTINGS_ENABLED", "true")
    get_settings.cache_clear()


def _disable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_SETTINGS_ENABLED", "false")
    get_settings.cache_clear()


def test_endpoints_are_absent_by_default(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Forced explicitly rather than relied on from the ambient .env — a
    # developer who enables dev settings locally would otherwise silently turn
    # this test into a no-op.
    _disable(monkeypatch)

    # 404, not 403: an endpoint that was never meant to exist should not even
    # confirm it exists.
    assert client.get("/api/dev/llm").status_code == 404
    assert client.put("/api/dev/llm", json={}).status_code == 404


def test_enabled_endpoint_never_echoes_the_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch)
    # The response is built from `get_settings()`, which reads the process CWD
    # .env — not the tmp file the fixture redirects writes to. So the key has
    # to be visible to Settings for the post-write readback to see it.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value-9999")
    get_settings.cache_clear()

    response = client.put(
        "/api/dev/llm",
        json={
            "api_key": "sk-super-secret-value-9999",
            "base_url": "https://example.invalid/v1",
            "model": "a-model",
        },
    )

    assert response.status_code == 200
    assert "super-secret" not in response.text
    payload = response.json()
    assert payload["configured"] is True
    assert payload["key_hint"] == "...9999"


def test_oversized_key_is_rejected_without_echoing_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FastAPI validates the body BEFORE the handler runs, so an over-long
    key produced a 422 whose `input` field echoed the whole secret — bypassing
    the 404 guard. Over-length is still a 422, but the body must not carry it.
    """
    monkeypatch.setattr(get_settings(), "dev_settings_enabled", False, raising=False)
    canary = "sk-LEAKCANARY" + ("x" * 600)

    response = client.put("/api/dev/llm", json={"api_key": canary})

    assert response.status_code in (404, 422)
    assert "LEAKCANARY" not in response.text


def test_a_newline_in_the_key_cannot_forge_an_env_line(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_upsert_env` writes line-oriented config, so a value containing a
    newline could append arbitrary settings — including re-enabling
    DEV_SETTINGS_ENABLED on a server where it is off."""
    _enable(monkeypatch)
    env = dev_settings._ENV_FILE

    response = client.put(
        "/api/dev/llm",
        json={"api_key": "sk-x\nDEV_SETTINGS_ENABLED=true", "base_url": "", "model": "m"},
    )

    assert response.status_code == 422
    assert "DEV_SETTINGS_ENABLED=true" not in env.read_text(encoding="utf-8")


def test_env_upsert_preserves_unrelated_lines(tmp_path, monkeypatch) -> None:
    """Only the three owned keys are rewritten; everything else in .env has to
    survive, or saving a key would quietly delete the rest of the config."""
    env = tmp_path / ".env"
    env.write_text(
        "DATABASE_URL=postgresql://x\n"
        "OPENAI_API_KEY=old-key-value\n"
        "# a comment\n"
        "JWT_SECRET=keepme\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dev_settings, "_ENV_FILE", env)

    dev_settings._upsert_env({"OPENAI_API_KEY": "new-key"})

    text = env.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=new-key" in text
    assert "DATABASE_URL=postgresql://x" in text
    assert "JWT_SECRET=keepme" in text
    assert "# a comment" in text


def test_env_upsert_appends_a_key_that_was_never_there(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("JWT_SECRET=keepme\n", encoding="utf-8")
    monkeypatch.setattr(dev_settings, "_ENV_FILE", env)

    dev_settings._upsert_env({"OPENAI_MODEL": "m"})

    text = env.read_text(encoding="utf-8")
    assert "OPENAI_MODEL=m" in text
    assert "JWT_SECRET=keepme" in text
