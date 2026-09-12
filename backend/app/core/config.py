from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Allergy AI Companion"
    database_url: str = "postgresql+asyncpg://allergy:allergy@localhost:5432/allergy_ai"
    redis_url: str = "redis://localhost:6379"

    # external services — keys stay server-side, never shipped to the frontend
    openai_api_key: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""
    pollen_api_key: str = ""
    weather_api_key: str = ""
    jwt_secret: str = "change-me"

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
