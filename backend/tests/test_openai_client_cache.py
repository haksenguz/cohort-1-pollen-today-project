"""The chat turn reuses one provider client instead of building one per request."""

from app.core import openai_client as oc
from app.core.config import get_settings


def test_the_same_settings_return_the_same_client(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test-cache", raising=False)
    oc.clear_client_cache()
    first = oc.get_openai_client_from_settings()
    second = oc.get_openai_client_from_settings()
    assert first is second
    oc.clear_client_cache()


def test_clearing_the_cache_builds_a_fresh_client(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test-cache", raising=False)
    oc.clear_client_cache()
    first = oc.get_openai_client_from_settings()
    oc.clear_client_cache()
    assert oc.get_openai_client_from_settings() is not first
    oc.clear_client_cache()


def test_a_changed_key_builds_a_different_client(monkeypatch):
    settings = get_settings()
    oc.clear_client_cache()
    monkeypatch.setattr(settings, "openai_api_key", "sk-one", raising=False)
    first = oc.get_openai_client_from_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-two", raising=False)
    assert oc.get_openai_client_from_settings() is not first
    oc.clear_client_cache()
