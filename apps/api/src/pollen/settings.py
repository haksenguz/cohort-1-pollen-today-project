"""Environment configuration, parsed once at import rather than read ad hoc.

Pydantic Settings is the Python counterpart of the Zod `AppConfig` schema: a
typo in `.env` fails at startup with a readable error, not at 07:00 in front of
subscribers.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pollen.libs.enums import Region, RiskLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = Field(alias="MONGODB_URI")
    port: int = Field(default=8000, alias="PORT")

    # Slice C — Telegram. Absent token means dry-run, not failure.
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_ops_chat_id: str | None = Field(default=None, alias="TELEGRAM_OPS_CHAT_ID")
    telegram_channels: dict[Region, str] = Field(default_factory=dict, alias="TELEGRAM_CHANNELS")

    # Slice A — KMA. Stored DECODED; the client percent-encodes it.
    kma_api_key: str | None = Field(default=None, alias="KMA_API_KEY")

    alert_min_risk_level: RiskLevel = Field(default=RiskLevel.HIGH, alias="ALERT_MIN_RISK_LEVEL")

    @field_validator("telegram_channels", mode="before")
    @classmethod
    def _parse_channels(cls, value: object) -> object:
        """`TELEGRAM_CHANNELS` arrives as a JSON string from the environment.

        Channel names are configuration, never code — adding a region is a
        deploy, not a release.
        """
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached so the file is read once per process."""
    return Settings()  # type: ignore[call-arg]
