"""Applications API router — list and create application records."""

from __future__ import annotations

from fastapi import APIRouter, Body

router = APIRouter(prefix="/applications", tags=["applications"])

# ---------------------------------------------------------------------------
# In-memory store keyed by user_id — replaced by Supabase in production.
# Tests use seed_applications() to pre-populate.
# ---------------------------------------------------------------------------

_applications_store: dict[str, list[dict]] = {}

# Legacy flat list kept for backwards compat with tests that use seed_applications
_application_store: list[dict] = []


def save_application(user_id: str, application: dict) -> None:
    """Persist an application record for a user."""
    if user_id not in _applications_store:
        _applications_store[user_id] = []
    record = dict(application)
    record.setdefault("user_id", user_id)
    _applications_store[user_id].append(record)
    # Also append to flat store so existing tests still pass
    _application_store.append(record)


def get_applications(user_id: str) -> list[dict]:
    """Return all application records for a user."""
    return _applications_store.get(user_id, [])


def seed_applications(records: list[dict]) -> None:
    """Replace the in-memory stores — used by tests."""
    global _application_store  # noqa: PLW0603
    _application_store.clear()
    _applications_store.clear()
    for record in records:
        uid = str(record.get("user_id", ""))
        if uid not in _applications_store:
            _applications_store[uid] = []
        _applications_store[uid].append(record)
    _application_store.extend(records)


# ---------------------------------------------------------------------------
# GET /applications
# ---------------------------------------------------------------------------


@router.get("")
async def list_applications(user_id: str):
    """List Application records for a user.

    Query params:
        user_id: Filter applications by user.

    Returns:
        JSON list of application dicts.
    """
    return get_applications(user_id)


# ---------------------------------------------------------------------------
# POST /applications
# ---------------------------------------------------------------------------


@router.post("")
async def create_application(
    user_id: str = Body(...),
    application: dict = Body(...),
):
    """Save an approved application record.

    Body:
        user_id:     The user this application belongs to.
        application: The application package dict to save.

    Returns:
        JSON with ``status: "saved"``.
    """
    save_application(user_id, application)
    return {"status": "saved"}
