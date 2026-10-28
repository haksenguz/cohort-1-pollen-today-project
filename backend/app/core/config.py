from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Where the app believes it is running. "production" turns on the boot guard
# in `production_readiness_problems`. Anything else is a typo, and a typo must
# not quietly mean "no guard".
ENVIRONMENTS = ("development", "production")

# Secrets that look like a secret and are not. A default that ships to
# production signs every session token with a value that is published in the
# repository, so anyone can mint a token for any user.
INSECURE_JWT_SECRETS = frozenset(
    {
        "change-me",
        "changeme",
        "change_me",
        "secret",
        "secretkey",
        "secret-key",
        "jwt-secret",
        "please-change-me",
    }
)

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Allergy AI Companion"

    # "development" by default so a local run never needs this set. A deploy
    # sets ENVIRONMENT=production, which is what makes the boot guard run.
    environment: str = "development"
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
    # Local-dev only. When true, `app.api.dev_settings` exposes an
    # unauthenticated route that can read and write this instance's model
    # credentials in backend/.env. That is only safe because this stays False
    # everywhere except a gitignored local .env — never set it in a deploy.
    dev_settings_enabled: bool = False
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

    # 제30조: the operator this app runs under. Both come from the
    # environment. Empty means the policy says plainly that no operator is
    # named yet, because a policy that names nobody is not a policy.
    operator_name: str = ""
    operator_registration_number: str = ""

    @field_validator("environment")
    @classmethod
    def _environment_is_known(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {list(ENVIRONMENTS)}, got {value!r}. "
                "An unknown value must not be read as 'no production guard'."
            )
        return normalised


def production_readiness_problems(settings: Settings) -> list[str]:
    """What would make this deployment unsafe. Empty list means ready.

    Each item is a mistake that does not error on its own. The stack starts,
    the health check passes, and the mistake only shows up later: a session
    forged with a published secret, or a route that hands out the provider key
    to whoever asks. A boot guard is the only place they can be caught.

    Outside production the list is empty. A local run on the example secret is
    a local run, and a guard that fires everywhere is a guard people disable.

    The provider keys are deliberately absent from this list. A missing LLM or
    pollen key degrades one feature and says so in the UI, which is honest.
    Stopping the deploy over it would not be.
    """
    if settings.environment != "production":
        return []

    problems: list[str] = []

    secret = settings.jwt_secret.strip()
    if not secret:
        problems.append("JWT_SECRET is empty. Generate one with `openssl rand -hex 32`.")
    elif secret.lower() in INSECURE_JWT_SECRETS or len(secret) < MIN_JWT_SECRET_LENGTH:
        problems.append(
            "JWT_SECRET is the example value or shorter than "
            f"{MIN_JWT_SECRET_LENGTH} characters. It signs every session token, so a "
            "known value lets anyone sign a token for any user. Generate one with "
            "`openssl rand -hex 32`."
        )

    if settings.dev_settings_enabled:
        problems.append(
            "DEV_SETTINGS_ENABLED is true. That route is unauthenticated and reads "
            "and writes this instance's provider credentials."
        )

    if settings.demo_mode:
        problems.append(
            "DEMO_MODE is true. Every request without a token is resolved to the "
            "seeded demo user, so the API has no authentication in front of it."
        )

    return problems


def assert_production_ready(settings: Settings) -> None:
    """Refuse to boot a production deployment with an unsafe configuration."""
    problems = production_readiness_problems(settings)
    if problems:
        joined = "\n  - ".join(problems)
        raise RuntimeError(f"Refusing to start in production mode:\n  - {joined}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
