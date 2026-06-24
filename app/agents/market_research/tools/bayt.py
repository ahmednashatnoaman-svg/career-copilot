"""
Bayt search tool.

Bayt has aggressive bot protection so we only use DDGS site: search.
No direct scraping attempted.
"""

import logging

from .web_search import search_jobs as ddgs_search

logger = logging.getLogger(__name__)


def search_jobs(role: str, location: str) -> list[dict]:
    """
    Search Bayt listings via DuckDuckGo site: filter.

    Returns:
        list of dicts with keys: title, url, snippet, source
    """
    raw = ddgs_search(role=role, location=location, site="bayt.com")

    results = []
    for item in raw:
        results.append({
            "title":        item.get("title", ""),
            "company":      "",
            "location":     location,
            "url":          item.get("url", ""),
            "snippet":      item.get("snippet", ""),
            "requirements": [],   # snippets only — no scraping
            "source":       "bayt",
        })

    logger.info(f"[bayt] '{role}' in '{location}' → {len(results)} results")
    return results