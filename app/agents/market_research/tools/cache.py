"""
tools/cache.py — Market Agent Cache
=====================================

WHAT THIS FILE DOES
-------------------
Stores and retrieves market research results to avoid redundant
tool calls. Same role + location + mode + lane = same data, so
we cache it and serve it to every user who asks.

STORAGE
-------
File-based JSON (cache.json in project root).
- Survives server restarts
- Zero extra dependencies
- Easy to inspect and clear manually
- Ready to swap for Redis/Postgres: just replace _read_store()
  and _write_store() — the rest of the API stays identical.

TTL (Time-To-Live)
------------------
Different lanes go stale at different rates (from constants.py):
    postings : 24h   (job listings change daily)
    trends   : 168h  (1 week)
    salary   : 720h  (30 days — CAPMAS data is slow-moving)

SCOPE
-----
Shared across all users. Market data for "Backend Developer in Cairo"
is the same regardless of who asks — no point fetching it twice.
Personalized data (CV matching, recommendations) should NOT be cached here.

TEAMMATES
---------
To swap storage backend in the future (Redis, Postgres, etc.):
    1. Replace _read_store() and _write_store() only
    2. Keep build_cache_key(), get_cached(), set_cache() signatures identical
    3. Update the module docstring
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

from app.agents.market_research.constants import (
    POSTINGS_TTL_HOURS,
    SALARIES_TTL_HOURS,
    TRENDS_TTL_HOURS,
)
from app.agents.market_research.schemas import LaneType

logger = logging.getLogger(__name__)

# Path to the cache file — sits next to the package root
_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "cache.json")

# Maps lane type to its TTL in hours
_TTL_BY_LANE: dict[LaneType, int] = {
    "postings": POSTINGS_TTL_HOURS,
    "trends":   TRENDS_TTL_HOURS,
    "salary":   SALARIES_TTL_HOURS,
}


# ---------------------------------------------------------------------------
# Storage backend (swap these two functions to change storage)
# ---------------------------------------------------------------------------

def _read_store() -> dict:
    """Read the full cache from disk. Returns empty dict if file missing."""
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.warning("[cache] cache.json is corrupted — starting fresh")
        return {}


def _write_store(store: dict) -> None:
    """Write the full cache to disk."""
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[cache] failed to write cache: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_cache_key(
    role: str,
    location: str,
    market_mode: str,
    lane: LaneType,
) -> str:
    """
    Build a deterministic cache key for a (role, location, mode, lane) combo.

    Example:
        build_cache_key("Backend Developer", "Cairo", "egypt", "postings")
        → "backend developer:cairo:egypt:postings"

    Lowercased so "Cairo" and "cairo" hit the same entry.
    """
    return f"{role.lower().strip()}:{location.lower().strip()}:{market_mode}:{lane}"


def get_cached(key: str, lane: LaneType) -> list[dict] | None:
    """
    Return cached data for a key if it exists and hasn't expired.

    Returns:
        list[dict] if cache hit and data is fresh
        None       if cache miss or data is stale

    Usage:
        data = get_cached(key, lane="postings")
        if data is None:
            data = fetch_from_tools(...)
            set_cache(key, data, lane="postings")
    """
    store = _read_store()
    entry = store.get(key)

    if entry is None:
        logger.debug(f"[cache] miss: {key}")
        return None

    # Check TTL
    cached_at = datetime.fromisoformat(entry["cached_at"])
    now = datetime.now(UTC)
    age_hours = (now - cached_at).total_seconds() / 3600
    ttl_hours = _TTL_BY_LANE.get(lane, POSTINGS_TTL_HOURS)

    if age_hours > ttl_hours:
        logger.debug(f"[cache] stale ({age_hours:.1f}h > {ttl_hours}h): {key}")
        return None

    logger.info(f"[cache] hit ({age_hours:.1f}h old): {key}")
    return entry["data"]


def set_cache(key: str, data: list[dict], lane: LaneType) -> None:
    """
    Store data under a key with the current timestamp.

    Only call this AFTER data has been validated — never cache
    raw, unvalidated tool output (a hallucinated claim could get
    cached and served to future users).

    Args:
        key  : from build_cache_key()
        data : validated list of dicts to cache
        lane : used to determine TTL on next read
    """
    store = _read_store()

    store[key] = {
        "data":      data,
        "cached_at": datetime.now(UTC).isoformat(),
        "lane":      lane,
    }

    _write_store(store)
    logger.info(f"[cache] stored {len(data)} items: {key}")


def invalidate(key: str) -> None:
    """
    Manually remove a single cache entry.

    Useful for testing or when you know a source has updated.
    """
    store = _read_store()
    if key in store:
        del store[key]
        _write_store(store)
        logger.info(f"[cache] invalidated: {key}")


def clear_all() -> None:
    """
    Wipe the entire cache.

    Use with caution — only for development/testing.
    """
    _write_store({})
    logger.warning("[cache] cache cleared")