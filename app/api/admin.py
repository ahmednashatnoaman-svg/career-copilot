"""Admin API — system stats and memory inspection."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.memory.longterm import recall

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin gate — checks profiles.is_admin in Supabase for the authenticated user
# ---------------------------------------------------------------------------


def require_admin(request: Request) -> None:
    """Raise 403 if the current user does not have is_admin = true in profiles.

    When Supabase is not configured (local dev / CI) the check is skipped so
    tests without credentials still pass.
    """
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is None:
        return  # no Supabase configured — skip in local dev / CI

    user_id: str = getattr(request.state, "user_id", "")
    if not user_id:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        result = (
            db.table("profiles")
            .select("is_admin")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not result.data or not result.data.get("is_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("require_admin profile lookup failed: %s", exc)
        raise HTTPException(status_code=403, detail="Admin access required") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_count(table: str, db) -> int:  # type: ignore[type-arg]
    try:
        resp = db.table(table).select("id", count="exact").execute()
        return resp.count or 0
    except Exception:  # noqa: BLE001
        return -1


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats", dependencies=[Depends(require_admin)])
def get_stats() -> dict[str, Any]:
    """Return system-wide counts and health indicators for the admin dashboard."""
    from app.api.applications import _application_store, _applications_store  # noqa: PLC0415
    from app.api.matches import _matches_store  # noqa: PLC0415
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()

    if db is not None:
        users = _safe_count("profiles", db)
        jobs = _safe_count("jobs", db)
        matches = _safe_count("matches", db)
        applications = _safe_count("applications", db)
        documents = _safe_count("documents", db)
        db_connected = True
    else:
        # Fall back to in-memory stores
        users = -1
        jobs = -1
        matches = sum(len(v) for v in _matches_store.values())
        applications = len(_application_store) + sum(len(v) for v in _applications_store.values())
        documents = -1
        db_connected = False

    return {
        "db_connected": db_connected,
        "counts": {
            "users": users,
            "jobs": jobs,
            "matches": matches,
            "applications": applications,
            "documents": documents,
        },
    }


@router.get("/memory/{user_id}", dependencies=[Depends(require_admin)])
def get_user_memory(user_id: str) -> dict[str, Any]:
    """Return all long-term memory facts stored for a user."""
    facts = recall(user_id)
    return {"user_id": user_id, "facts": facts, "count": len(facts)}


@router.delete("/memory/{user_id}/{key}", dependencies=[Depends(require_admin)])
def delete_memory_key(user_id: str, key: str) -> dict[str, str]:
    """Delete a single long-term memory key for a user."""
    try:
        from app.memory.checkpointer import store_cm  # noqa: PLC0415

        with store_cm() as store:
            store.delete(("user", user_id), key)
        return {"status": "deleted", "user_id": user_id, "key": key}
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_memory_key failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
