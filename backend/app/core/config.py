from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    """Runtime configuration, read from the environment.

    Every value here is required unless it has a safe default. A missing
    secret raises at import time so the process dies on startup rather than
    serving traffic with a placeholder key — a config error should look like
    a crash, not a security incident discovered weeks later.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Reject unknown keys: a typo'd FOO_URL should fail loudly rather than
        # sit unread while the real setting silently keeps its default.
        extra="forbid",
    )

    # ---- app ----
    environment: Environment = "local"
    debug: bool = False
    project_name: str = "E-Commerce API"
    api_v1_prefix: str = "/api/v1"

    # ---- secrets (no defaults, by design) ----
    secret_key: SecretStr = Field(
        ...,
        min_length=32,
        description="Signing key for JWTs. 32+ chars; generate with `openssl rand -hex 32`.",
    )
    database_url: str = Field(..., description="Async DSN: postgresql+asyncpg://...")
    redis_url: str = Field(..., description="redis://host:port/db")

    # ---- auth ----
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    jwt_algorithm: str = "HS256"

    # ---- database pool ----
    db_pool_size: int = 10
    db_max_overflow: int = 10

    # ---- cors ----
    cors_origins: list[str] = Field(default_factory=list)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """The same database over a sync driver, for Alembic.

        Derived rather than configured separately: two independent env vars
        eventually drift, and migrations silently running against the wrong
        database is a very bad afternoon.
        """
        return self.database_url.replace("+asyncpg", "+psycopg")

    @model_validator(mode="after")
    def _require_async_driver(self) -> Self:
        """Reject a DSN without the async driver rather than rewriting it.

        A bare `postgresql://` works for the app only if something patches the
        driver in at call time — and then sync_database_url's `+asyncpg` ->
        `+psycopg` swap silently no-ops, handing Alembic an async URL. Failing
        here points at the actual mistake: the environment.
        """
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "database_url must start with 'postgresql+asyncpg://' "
                f"(got {self.database_url.split('://')[0]}://...)"
            )
        return self

    @model_validator(mode="after")
    def _forbid_debug_in_production(self) -> Self:
        if self.is_production and self.debug:
            raise ValueError(
                "debug must be false in production: it exposes tracebacks and "
                "internal state to clients"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor — the environment is read once per process.

    Used as a FastAPI dependency so tests can override it via
    `app.dependency_overrides` without touching os.environ.
    """
    return Settings()
