# E-Commerce Backend

FastAPI + Strawberry GraphQL + PostgreSQL. Built test-first.

## Requirements

- Python 3.12 (pinned via `.python-version`; `uv` installs it)
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose

## Setup

```bash
uv sync
cp .env.example .env   # then fill in real local values
```

## Common commands

| Task | Command |
|---|---|
| Run the API | `uv run uvicorn app.main:app --reload` |
| Full test suite (with coverage gate) | `uv run pytest` |
| One file, no coverage gate | `uv run pytest tests/e2e/test_health.py --no-cov` |
| Lint | `uv run ruff check .` |
| Autofix + format | `uv run ruff check --fix . && uv run ruff format .` |
| Types | `uv run mypy app` |
| All gates | `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest` |

## Layout

```
app/
├── main.py          # app factory
├── core/            # config, security, logging
├── db/              # engine, session, declarative base
├── models/          # SQLAlchemy models
├── repositories/    # the only layer that touches the ORM
├── services/        # business rules
├── graphql/         # schema, types, dataloaders, permissions
├── api/             # REST edge: health, webhooks, uploads
└── workers/         # ARQ background tasks
tests/{unit,integration,e2e}/
```

## Conventions

- **Tests first.** Red → green → refactor → commit.
- **No secrets in git.** `.env` is ignored; `.env.example` documents the keys.
- **Money is `NUMERIC(12,2)`**, never float.
- **Timezone-aware datetimes only** (ruff `DTZ` enforces this).
