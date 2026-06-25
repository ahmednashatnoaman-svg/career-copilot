"""Applications API router — list and create application records."""

from __future__ import annotations

from fastapi import APIRouter, Body

router = APIRouter(prefix="/applications", tags=["applications"])

# ---------------------------------------------------------------------------
# In-memory fallback (used when Supabase is not configured or in tests)
# ---------------------------------------------------------------------------

_applications_store: dict[str, list[dict]] = {}
_application_store: list[dict] = []


def save_application(user_id: str, application: dict) -> None:
    """Persist an application record. Supabase if configured, else in-memory."""
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            db.table("applications").insert(
                {
                    "user_id": user_id,
                    "company": application.get("company", ""),
                    "job_title": application.get("job_title", application.get("title", "")),
                    "cover_letter": application.get("cover_letter", ""),
                    "tailored_cv": application.get("tailored_cv", ""),
                    "email_draft": application.get("email_draft", ""),
                    "status": application.get("status", "APPROVED"),
                }
            ).execute()
            return
        except Exception:  # noqa: BLE001
            pass

    # In-memory fallback
    record = dict(application)
    record.setdefault("user_id", user_id)
    _applications_store.setdefault(user_id, []).append(record)
    _application_store.append(record)


def get_applications(user_id: str) -> list[dict]:
    """Return all applications for a user. Supabase if configured, else in-memory."""
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            result = (
                db.table("applications")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception:  # noqa: BLE001
            pass
    return _applications_store.get(user_id, [])


def seed_applications(records: list[dict]) -> None:
    """Replace the in-memory stores — used by integration tests."""
    global _application_store  # noqa: PLW0603
    _application_store.clear()
    _applications_store.clear()
    for record in records:
        uid = str(record.get("user_id", ""))
        _applications_store.setdefault(uid, []).append(record)
    _application_store.extend(records)


# ---------------------------------------------------------------------------
# GET /applications
# ---------------------------------------------------------------------------


@router.get("")
async def list_applications(user_id: str):
    return get_applications(user_id)


# ---------------------------------------------------------------------------
# POST /applications
# ---------------------------------------------------------------------------


@router.post("")
async def create_application(
    user_id: str = Body(...),
    application: dict = Body(...),
):
    save_application(user_id, application)
    return {"status": "saved"}
