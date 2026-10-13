import pytest
from pydantic import ValidationError

from app.core.config import Settings

pytestmark = pytest.mark.unit

# A complete, valid environment. Tests remove or override one key at a time
# to prove that key is genuinely enforced.
VALID_ENV = {
    "ENVIRONMENT": "local",
    "SECRET_KEY": "s" * 32,
    "DATABASE_URL": "postgresql+asyncpg://user:pw@localhost:5432/shop",
    "REDIS_URL": "redis://localhost:6379/0",
}

REQUIRED_KEYS = ["SECRET_KEY", "DATABASE_URL", "REDIS_URL"]


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """A clean, valid environment — the only config source during tests.

    Two forms of isolation, both load-bearing:

    1. Every key is deleted before the valid ones are set, so a variable
       exported in the developer's shell cannot make a test pass that would
       fail in CI.
    2. `_env_file=None` disables .env loading. Without it, a developer's real
       .env would satisfy the very keys a test is trying to remove, and the
       missing-secret tests would silently stop testing anything.
    """
    for key in (*VALID_ENV, "DEBUG"):
        monkeypatch.delenv(key, raising=False)
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    return monkeypatch


def test_settings_load_from_environment(env: pytest.MonkeyPatch) -> None:
    settings = Settings()

    assert settings.environment == "local"
    assert settings.database_url == VALID_ENV["DATABASE_URL"]
    assert settings.redis_url == VALID_ENV["REDIS_URL"]


@pytest.mark.parametrize("missing", REQUIRED_KEYS)
def test_missing_required_secret_raises(env: pytest.MonkeyPatch, missing: str) -> None:
    """The app must refuse to start, not boot with a silent default."""
    env.delenv(missing)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert missing.lower() in str(exc_info.value).lower()


def test_short_secret_key_is_rejected(env: pytest.MonkeyPatch) -> None:
    """A 32-char floor: long enough that an HS256 signing key isn't guessable."""
    env.setenv("SECRET_KEY", "too-short")

    with pytest.raises(ValidationError):
        Settings()


def test_secret_key_is_not_exposed_in_repr(env: pytest.MonkeyPatch) -> None:
    """Settings get logged and appear in tracebacks — the key must not ride along."""
    settings = Settings()

    assert VALID_ENV["SECRET_KEY"] not in repr(settings)
    assert settings.secret_key.get_secret_value() == VALID_ENV["SECRET_KEY"]


def test_production_rejects_debug(env: pytest.MonkeyPatch) -> None:
    """Debug mode in production leaks tracebacks and internals to users."""
    env.setenv("ENVIRONMENT", "production")
    env.setenv("DEBUG", "true")

    with pytest.raises(ValidationError, match="debug"):
        Settings()


def test_unknown_environment_is_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("ENVIRONMENT", "staging-typo")

    with pytest.raises(ValidationError):
        Settings()


def test_sync_database_url_derived_for_alembic(env: pytest.MonkeyPatch) -> None:
    """Alembic runs sync, the app runs async: one source of truth, two drivers."""
    settings = Settings()

    assert settings.sync_database_url.startswith("postgresql+psycopg://")
    assert "asyncpg" not in settings.sync_database_url


def test_is_production_flag(env: pytest.MonkeyPatch) -> None:
    assert Settings().is_production is False

    env.setenv("ENVIRONMENT", "production")
    assert Settings().is_production is True
