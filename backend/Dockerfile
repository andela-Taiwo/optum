# syntax=docker/dockerfile:1

# uv is pinned to the version that produced uv.lock. A mismatched uv can
# interpret the lockfile differently, which is exactly the drift the lockfile
# exists to prevent.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /usr/local/bin/

# --- deps layer: dependencies install without the source, so editing code
# doesn't invalidate the (slow) dependency layer ---
FROM base AS deps
WORKDIR /app
COPY pyproject.toml uv.lock ./
# No `|| uv sync` fallback: if the lockfile is stale the build must fail, not
# quietly resolve different versions than CI tested against.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# --- build layer: install the project itself into the venv ---
# Without this the venv holds dependencies but not the `app` package, and the
# container starts only to die on ModuleNotFoundError. Separate stage so the
# dependency cache above still does its job.
FROM deps AS build
WORKDIR /app
# README.md is required: pyproject declares `readme = "README.md"` and the
# build backend reads it.
COPY README.md ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- final runtime image ---
FROM base AS runtime
RUN groupadd -r app && useradd -r -g app -d /app app
WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY app ./app
COPY pyproject.toml README.md ./

# Put the venv first on PATH so `uvicorn` resolves without `uv run`, which
# would otherwise try to re-sync at container start.
ENV PATH="/app/.venv/bin:$PATH"

# No secrets are baked in: every credential arrives at runtime from the
# environment. There is deliberately no COPY of .env, and .dockerignore
# excludes it so it cannot be pulled in by accident.
USER app

EXPOSE 8000

# Matches the route the app actually serves (app/api/health.py).
# urlopen raises on non-2xx, so a 500 fails the check.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else sys.exit(1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
