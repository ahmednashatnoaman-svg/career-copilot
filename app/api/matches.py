"""Matches API router — list and save job match results."""

from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/matches", tags=["matches"])

# In-memory matches store keyed by user_id (replace with Supabase later)
_matches_store: dict[str, list[dict]] = {}


def save_matches(user_id: str, matches: list[dict]) -> None:
    """Persist match results for a user."""
    _matches_store[user_id] = matches


def get_matches(user_id: str) -> list[dict]:
    """Return all match results for a user."""
    return _matches_store.get(user_id, [])


@router.get("/")
async def list_matches(user_id: str = Query(...)):
    """List job match results for a user.

    Query params:
        user_id: The user whose matches to retrieve.

    Returns:
        JSON list of match result dicts.
    """
    return get_matches(user_id)


@router.post("/")
async def save_user_matches(user_id: str, matches: list[dict]):
    """Save job match results for a user.

    Body:
        user_id: The user's ID.
        matches: List of match result dicts to save.

    Returns:
        JSON with ``saved`` count.
    """
    save_matches(user_id, matches)
    return {"saved": len(matches)}
