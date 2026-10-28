"""A deployment must refuse to start on a configuration that is unsafe.

Each of these mistakes is invisible once the stack is running. The process
starts, the health check answers 200, the site loads, and the damage shows up
later: a session token anyone can mint, or a route that hands the provider key
to whoever asks for it. Nothing crashes, so nothing reports it.

The one place they can be caught is the boot, before the first request. That is
what this file tests.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app import main
from app.core.config import (
    Settings,
    assert_production_ready,
    production_readiness_problems,
)

GOOD_SECRET = "3f9a1c7e5b2d8064ae31f7c9d2b58046ae31f7c9d2b58046ae31f7c9d2b5804"


def _settings(**overrides) -> Settings:
    base = {
        "environment": "production",
        "jwt_secret": GOOD_SECRET,
        "dev_settings_enabled": False,
        "demo_mode": False,
    }
    base.update(overrides)
    return Settings(**base)


# --- the secret that signs every session token ----------------------------


@pytest.mark.parametrize(
    "secret",
    [
        "change-me",
        "CHANGE-ME",
        "change_me",
        "secret",
        "jwt-secret",
        "",
        "   ",
        "short",
        "a" * 31,
    ],
    ids=[
        "the-example-value",
        "uppercase-example",
        "underscore-example",
        "secret",
        "jwt-secret",
        "empty",
        "blank",
        "short",
        "one-under-the-limit",
    ],
)
def test_a_weak_jwt_secret_is_a_production_problem(secret: str) -> None:
    """The default is the value that ships in the code, so shipping the
    default is shipping a published signing key.
    """
    problems = production_readiness_problems(_settings(jwt_secret=secret))
    assert any("JWT_SECRET" in problem for problem in problems), (
        f"jwt secret {secret!r} was accepted in production"
    )


def test_a_long_random_secret_is_accepted() -> None:
    assert production_readiness_problems(_settings(jwt_secret=GOOD_SECRET)) == []


def test_the_length_boundary_is_exactly_32() -> None:
    assert production_readiness_problems(_settings(jwt_secret="a" * 32)) == []
    assert production_readiness_problems(_settings(jwt_secret="a" * 31)) != []


# --- the routes that must be off -------------------------------------------


def test_the_dev_credential_route_is_a_production_problem() -> None:
    """`app.api.dev_settings` is unauthenticated and reads and writes the
    provider credentials in the instance's environment.
    """
    problems = production_readiness_problems(_settings(dev_settings_enabled=True))
    assert any("DEV_SETTINGS_ENABLED" in problem for problem in problems)


def test_demo_mode_is_a_production_problem() -> None:
    """Demo mode resolves every request without a token to the seeded user, so
    the API has no authentication in front of it at all.
    """
    problems = production_readiness_problems(_settings(demo_mode=True))
    assert any("DEMO_MODE" in problem for problem in problems)


# --- missing provider keys are not a reason to stop -----------------------


def test_a_missing_llm_key_does_not_stop_the_deploy() -> None:
    """A blank provider key disables one feature and the UI says so, which is
    honest. Refusing to boot over it would push people to paste a key they do
    not have into a file they do not understand.
    """
    problems = production_readiness_problems(_settings(openai_api_key="", pollen_api_key=""))
    assert problems == []


# --- the environment switch itself -----------------------------------------


def test_development_is_never_guarded() -> None:
    """A local run on the example secret is a local run."""
    settings = _settings(environment="development", jwt_secret="change-me")
    assert production_readiness_problems(settings) == []


def test_an_unknown_environment_is_rejected() -> None:
    """A typo must not read as "no guard".

    If ENVIRONMENT=prodtypo were accepted and simply not equal to
    "production", the guard would be off and nothing would say so.
    """
    with pytest.raises(ValidationError):
        _settings(environment="prodtypo")


def test_the_environment_value_is_case_insensitive() -> None:
    assert _settings(environment="PRODUCTION").environment == "production"


# --- the wiring ------------------------------------------------------------


def test_the_app_refuses_to_boot_with_an_unsafe_production_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard has to be on the boot path, not just in a module nobody calls.

    The check runs before the database is touched, so this test needs no
    database and cannot be affected by one being down.
    """
    monkeypatch.setattr(main, "settings", _settings(jwt_secret="change-me"))

    async def _enter_lifespan() -> None:
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        asyncio.run(_enter_lifespan())


def test_the_error_names_every_problem_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixing one mistake per deploy is how a deploy takes three rounds."""
    monkeypatch.setattr(
        main, "settings", _settings(jwt_secret="change-me", dev_settings_enabled=True)
    )

    async def _enter_lifespan() -> None:
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(_enter_lifespan())

    message = str(caught.value)
    assert "JWT_SECRET" in message
    assert "DEV_SETTINGS_ENABLED" in message


def test_assert_production_ready_is_silent_when_the_config_is_safe() -> None:
    assert_production_ready(_settings())
