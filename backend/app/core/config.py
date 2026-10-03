from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Allergy AI Companion"
    database_url: str = "postgresql+asyncpg://allergy:allergy@localhost:5432/allergy_ai"
    redis_url: str = "redis://localhost:6379"

    # external services — keys stay server-side, never shipped to the frontend
    openai_api_key: str = ""
    # Optional OpenAI-compatible proxy (OpenRouter, Azure OpenAI, local llama.cpp
    # server, etc). Empty means use OpenAI's default endpoint.
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    # J6 cost + latency guard: hard ceiling on output tokens per call and a
    # per-call timeout. 0 falls back to the client module's defaults.
    openai_max_tokens: int = 0
    openai_timeout_seconds: float = 0.0
    naver_client_id: str = ""
    naver_client_secret: str = ""
    pollen_api_key: str = ""
    jwt_secret: str = "change-me"

    # Abuse protection for POST /api/chat. Every turn is a real model call, so
    # an unbounded endpoint is a direct billing risk. Per-user, per-process,
    # sliding window — see app/core/rate_limit.py for the (documented) limits
    # of that choice. 0 or less disables limiting, which is what local dev and
    # the test suite use.
    chat_rate_limit_per_minute: int = 20

    cors_origins: list[str] = ["http://localhost:3000"]

    # ADR 0003: when DEMO_MODE is on, requests without a bearer token are
    # resolved to a seeded demo user instead of 401'ing. The frontend's
    # phone preview / demo path relies on this so /api/alerts and friends
    # work without a full register+login round-trip. Off by default;
    # only ever turned on for local demo runs.
    demo_mode: bool = False
    demo_user_email: str = "demo@local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
