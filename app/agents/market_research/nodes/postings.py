"""
nodes/postings.py — Job Postings Lane Node
==========================================

WHAT THIS FILE DOES
-------------------
Fetches job postings for every LaneQuery where lane == "postings".
Writes a list of validated JobPosting objects to state["postings"].

FLOW PER QUERY
--------------
    1. Build cache key
    2. Cache hit  → deserialize and return cached JobPostings
    3. Cache miss → call ALL tools for the market_mode
                    each tool is wrapped in try/except — one
                    failing source never kills the whole node
    4. Convert raw tool dicts → JobPosting Pydantic models
    5. Store validated results in cache
    6. Return {"postings": [...]}

TOOL ROUTING
------------
    egypt        → wuzzuf + bayt
    freelance    → upwork (API or web fallback — see tools/upwork.py)
    international→ adzuna (API or web fallback — see tools/adzuna.py)

TEAMMATES
---------
- To add a new source: add a branch in _fetch_raw() only.
- To change the JobPosting schema: update schemas.py + _to_job_posting().
- Cache TTL is set in constants.py (POSTINGS_TTL_HOURS).
- API keys live in .env — see tools/adzuna.py and tools/upwork.py.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.agents.market_research.schemas import JobPosting, LaneQuery, MarketMode, Source
from app.agents.market_research.state import MarketAgentState
from app.agents.market_research.tools import adzuna, bayt, upwork, wuzzuf
from app.agents.market_research.tools.cache import build_cache_key, get_cached, set_cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool routing — one function per source, all wrapped in try/except
# ---------------------------------------------------------------------------

def _fetch_raw(role: str, location: str | None, mode: MarketMode) -> list[dict]:
    """
    Call ALL tools for the given market_mode.

    Each source is called independently — if one fails the others
    still run. Returns a flat merged list of raw dicts.
    """
    loc     = location or ""
    results = []

    if mode == "egypt":
        for source_name, fn, kwargs in [
            ("wuzzuf", wuzzuf.search_jobs, {"role": role, "location": loc}),
            ("bayt",   bayt.search_jobs,   {"role": role, "location": loc}),
        ]:
            try:
                items = fn(**kwargs)
                results.extend(items)
                logger.info(f"[postings] {source_name} → {len(items)} results")
            except Exception as e:
                logger.warning(f"[postings] {source_name} failed: {e}")

    elif mode == "freelance":
        try:
            query = f"{role} {loc}".strip()
            items = upwork.search_jobs(query=query)
            results.extend(items)
            logger.info(f"[postings] upwork → {len(items)} results")
        except Exception as e:
            logger.warning(f"[postings] upwork failed: {e}")

    elif mode == "international":
        try:
            items = adzuna.search_jobs(role=role, location=loc)
            results.extend(items)
            logger.info(f"[postings] adzuna → {len(items)} results")
        except Exception as e:
            logger.warning(f"[postings] adzuna failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Raw dict → Pydantic model
# ---------------------------------------------------------------------------

def _to_job_posting(raw: dict) -> JobPosting | None:
    """
    Convert a raw tool dict into a JobPosting model.

    Returns None if the dict is missing required fields (title or url)
    so callers can filter with: [p for p in map(_to_job_posting, raw) if p]

    Confidence baseline: 0.7 for all scraped/searched results.
    validator_node can revise this downward for low-quality sources.
    """
    title = raw.get("title", "").strip()
    url   = raw.get("url",   "").strip()

    if not title or not url:
        return None

    try:
        return JobPosting(
            title       = title,
            company     = raw.get("company", ""),
            location    = raw.get("location", ""),
            description = raw.get("snippet") or None,
            source      = Source(
                name         = raw.get("source", "unknown"),
                url          = url,
                retrieved_at = datetime.now(UTC),
            ),
            confidence = 0.7,
        )
    except Exception as e:
        logger.warning(f"[postings] failed to build JobPosting from {raw}: {e}")
        return None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def postings_node(state: MarketAgentState) -> dict:
    """
    LangGraph node — fetches job postings for all postings-lane queries.

    Reads  : state["lane_queries"]
    Writes : state["postings"]  (appended via reducer — see state.py)
    """
    all_postings: list[JobPosting] = []

    queries: list[LaneQuery] = [
        (LaneQuery(**q) if isinstance(q, dict) else q)
        for q in state.get("lane_queries", [])
        if (q.get("lane") if isinstance(q, dict) else q.lane) == "postings"
    ]

    if not queries:
        logger.warning("[postings] no postings queries found in lane_queries")
        return {"postings": []}

    for query in queries:
        cache_key = build_cache_key(
            role        = query.role,
            location    = query.location or "",
            market_mode = query.market_mode,
            lane        = "postings",
        )

        # --- 1. Cache check ---
        cached = get_cached(cache_key, lane="postings")
        if cached is not None:
            postings = [_to_job_posting(item) for item in cached]
            all_postings.extend(p for p in postings if p)
            continue

        # --- 2. Cache miss — fetch from all tools for this mode ---
        logger.info(
            f"[postings] fetching: role={query.role!r} "
            f"mode={query.market_mode} location={query.location!r}"
        )
        raw_results = _fetch_raw(
            role     = query.role,
            location = query.location,
            mode     = query.market_mode,
        )

        # --- 3. Convert to JobPosting models ---
        postings = [_to_job_posting(r) for r in raw_results]
        postings = [p for p in postings if p]

        # --- 4. Cache raw results (re-parsed on cache hit) ---
        if postings:
            set_cache(key=cache_key, data=raw_results, lane="postings")

        all_postings.extend(postings)
        logger.info(
            f"[postings] done: role={query.role!r} "
            f"mode={query.market_mode} → {len(postings)} postings"
        )

    return {"postings": [p.model_dump(mode="json") for p in all_postings]}