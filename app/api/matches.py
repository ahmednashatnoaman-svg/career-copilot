"""Matches API router — list and save job match results."""

from __future__ import annotations

from fastapi import APIRouter, Body, Request

router = APIRouter(prefix="/matches", tags=["matches"])

# In-memory fallback (used when Supabase is not configured or in tests)
_matches_store: dict[str, list[dict]] = {}


def save_matches(user_id: str, matches: list[dict]) -> None:
    """Persist match results. Supabase if configured, else in-memory."""
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            # Delete old matches for this user and insert fresh ones
            db.table("matches").delete().eq("user_id", user_id).execute()
            rows = []
            for m in matches:
                job_id = m.get("job_id")
                if not job_id:
                    # Upsert the job row first
                    job_resp = (
                        db.table("jobs")
                        .insert(
                            {
                                "title": m.get("title", ""),
                                "company": m.get("company", ""),
                                "url": m.get("url", ""),
                                "snippet": m.get("snippet", ""),
                                "source": m.get("source", ""),
                            }
                        )
                        .execute()
                    )
                    job_id = job_resp.data[0]["id"] if job_resp.data else None
                if job_id:
                    rows.append(
                        {
                            "user_id": user_id,
                            "job_id": job_id,
                            "score": float(m.get("score", 0.0)),
                            "reasons": m.get("reasons", []),
                        }
                    )
            if rows:
                db.table("matches").insert(rows).execute()
            return
        except Exception:  # noqa: BLE001
            pass
    _matches_store[user_id] = matches


def get_matches(user_id: str) -> list[dict]:
    """Return match results for a user. Supabase if configured, else in-memory."""
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            result = (
                db.table("matches")
                .select("*, jobs(*)")
                .eq("user_id", user_id)
                .order("score", desc=True)
                .execute()
            )
            # Flatten the joined job data into the match dict
            rows = []
            for row in (result.data or []):
                job = row.pop("jobs", {}) or {}
                rows.append(
                    {
                        "job_id": row.get("job_id"),
                        "score": row.get("score"),
                        "reasons": row.get("reasons", []),
                        "title": job.get("title", ""),
                        "company": job.get("company", ""),
                        "url": job.get("url", ""),
                        "snippet": job.get("snippet", ""),
                    }
                )
            return rows
        except Exception:  # noqa: BLE001
            pass
    return _matches_store.get(user_id, [])


@router.get("/")
async def list_matches(request: Request):
    user_id: str = getattr(request.state, "user_id", "")
    return get_matches(user_id)


@router.post("/")
async def save_user_matches(request: Request, matches: list[dict] = Body(...)):  # noqa: B008
    user_id: str = getattr(request.state, "user_id", "")
    save_matches(user_id, matches)
    return {"saved": len(matches)}
