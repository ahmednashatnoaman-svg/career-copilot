"""Applications API router — list application rows."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/applications", tags=["applications"])

# ---------------------------------------------------------------------------
# In-memory stub store — replaced by real DB session in production.
# Tests use this directly without needing Postgres.
# ---------------------------------------------------------------------------

_application_store: list[dict] = []


def _get_application_store() -> list[dict]:
    return _application_store


def seed_applications(records: list[dict]) -> None:
    """Replace the in-memory store — used by tests."""
    global _application_store  # noqa: PLW0603
    _application_store.clear()
    _application_store.extend(records)


# ---------------------------------------------------------------------------
# GET /applications
# ---------------------------------------------------------------------------


@router.get("")
async def list_applications(user_id: str):
    """List Application records for a user.

    In production this would query the DB via SQLAlchemy.
    The in-memory store is used for unit tests.

    Query params:
        user_id: Filter applications by user.

    Returns:
        JSON list of application dicts.
    """
    store = _get_application_store()
    return [a for a in store if str(a.get("user_id")) == str(user_id)]
