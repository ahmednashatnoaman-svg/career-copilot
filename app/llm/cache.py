"""LLM response cache.

Wires LangChain's global LLM cache so repeated identical prompts at
temperature=0 are served from cache instead of re-hitting the API.

Usage
-----
Call ``wire_cache()`` once at application startup (e.g. from ``app/llm/__init__.py``).
The cache is transparent to all ``get_llm()`` callers — no code changes needed.

Cache backend
-------------
Uses LangChain's ``InMemoryCache`` by default (zero-dependency, process-scoped).
Set ``LLM_CACHE_BACKEND=sqlite`` in .env to persist across restarts via
``SQLiteCache`` (requires no extra packages — uses stdlib sqlite3).
"""

from __future__ import annotations

import os

import langchain_core.globals as _lc_globals


def wire_cache(backend: str | None = None) -> None:
    """Configure LangChain's global LLM cache.

    Safe to call multiple times — subsequent calls are no-ops if the cache
    is already wired.

    Parameters
    ----------
    backend:
        ``"memory"`` (default) or ``"sqlite"``.  Falls back to the
        ``LLM_CACHE_BACKEND`` environment variable, then ``"memory"``.
    """
    if _lc_globals.get_llm_cache() is not None:
        return  # already wired

    resolved = backend or os.environ.get("LLM_CACHE_BACKEND", "memory")

    if resolved == "sqlite":
        from langchain_community.cache import SQLiteCache  # type: ignore[import]

        db_path = os.environ.get("LLM_CACHE_DB", ".langchain_cache.db")
        cache = SQLiteCache(database_path=db_path)
    else:
        from langchain_core.caches import InMemoryCache

        cache = InMemoryCache()

    _lc_globals.set_llm_cache(cache)
