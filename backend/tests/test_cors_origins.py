"""The API has to allow the origin the site is actually served from.

The shipped stack serves the PWA and the API from one origin, so a normal
deploy needs no CORS entry at all. The danger is the opposite case: a deploy
that sets CORS_ORIGINS to the wrong value, and then every request from the
browser fails with an error that reads like a backend problem. The public
origin joins the allowlist by itself, so that mistake cannot take the site
down.
"""

from __future__ import annotations

from app.core.config import Settings


def test_the_public_origin_is_allowed_without_being_configured() -> None:
    settings = Settings(
        _env_file=None, environment="production", public_origin="https://allergy.example.com"
    )
    assert "https://allergy.example.com" in settings.cors_origins


def test_a_trailing_slash_does_not_make_a_second_origin() -> None:
    settings = Settings(
        _env_file=None, environment="production", public_origin="https://allergy.example.com/"
    )
    assert settings.cors_origins.count("https://allergy.example.com") == 1


def test_an_origin_that_is_already_listed_is_not_added_twice() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        public_origin="https://allergy.example.com",
        cors_origins=["https://allergy.example.com"],
    )
    assert settings.cors_origins.count("https://allergy.example.com") == 1


def test_a_listed_origin_survives_the_public_origin() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        public_origin="https://allergy.example.com",
        cors_origins=["https://admin.example.com"],
    )
    assert "https://admin.example.com" in settings.cors_origins
    assert "https://allergy.example.com" in settings.cors_origins


def test_a_production_run_with_nothing_configured_allows_nothing() -> None:
    # Same origin, so no CORS entry is needed, and a production deployment
    # must not inherit the development origins.
    settings = Settings(_env_file=None, environment="production")
    assert settings.cors_origins == []


def test_a_local_run_falls_back_to_the_local_origins() -> None:
    settings = Settings(_env_file=None, environment="development")
    assert "http://localhost:5173" in settings.cors_origins
    assert "http://localhost:3000" in settings.cors_origins
