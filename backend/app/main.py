from fastapi import FastAPI

from app.api import health


def create_app() -> FastAPI:
    """Application factory.

    A factory rather than a module-level singleton so tests can build an
    isolated app per fixture, and so settings/overrides can be injected
    without import-time side effects.
    """
    app = FastAPI(title="E-Commerce API", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
