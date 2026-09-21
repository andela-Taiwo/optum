from typing import Literal

from fastapi import APIRouter

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, Literal["ok"]]:
    """Liveness probe: the process is up and serving requests.

    Deliberately does not touch Postgres or Redis — a liveness check that
    depends on downstream services causes restart storms when they blip.
    Dependency checks belong in /ready (added with the DB layer in Phase 1).
    """
    return {"status": "ok"}
