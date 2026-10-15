import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

# Settings is required-by-design and has no defaults for secrets, so importing
# anything that builds it fails without an environment. Rather than requiring
# every CI job to remember the full set, fill in test-safe values for whatever
# is absent — set BEFORE app imports, since Settings is read at import time.
#
# setdefault, not assignment: a value already exported (CI's DATABASE_URL
# pointing at the service container, say) always wins.
_TEST_ENV_DEFAULTS = {
    "ENVIRONMENT": "test",
    "SECRET_KEY": "test-only-not-a-real-secret-0123456789abcdef",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:55432/ecommerce",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

from app.main import create_app  # noqa: E402  (must follow the env setup above)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """An HTTP client wired directly to the ASGI app — no network, no live server."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
