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


@lru_cache
def get_settings() -> Settings:
    return Settings()
