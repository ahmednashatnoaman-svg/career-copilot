"""
Web search tool using DuckDuckGo (free, no API key needed).
"""

import logging
import time

from ddgs import DDGS

logger = logging.getLogger(__name__)

# How long to wait between searches to avoid rate limiting
_RATE_LIMIT_DELAY = 1.5


def search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search DuckDuckGo and return structured results.

    Returns:
        list of dicts with keys: title, url, snippet
    """
    try:
        time.sleep(_RATE_LIMIT_DELAY)

        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)

        results = []
        for item in raw:
            results.append({
                "title":   item.get("title", ""),
                "url":     item.get("href", ""),
                "snippet": item.get("body", ""),
            })

        logger.info(f"[web_search] '{query}' → {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"[web_search] failed for '{query}': {e}")
        return []


def search_jobs(role: str, location: str, site: str | None = None) -> list[dict]:
    """
    Convenience wrapper for job-specific searches.

    Args:
        role:     e.g. "AI engineer"
        location: e.g. "Cairo Egypt"
        site:     optional site filter e.g. "wuzzuf.net"

    Returns:
        list of dicts with keys: title, url, snippet
    """
    if site:
        query = f'site:{site} {role} {location}'
    else:
        query = f'{role} jobs {location}'

    return search(query, max_results=2)


def search_salaries(role: str, location: str) -> list[dict]:
    """
    Search for salary data for a role in a location.
    Tries both English and Arabic queries for Egyptian market coverage.
    """
    results = []

    english_query = f'{role} salary {location} 2025'
    results += search(english_query, max_results=5)

    # Arabic query hits local forums, Wuzzuf blog, LinkedIn Arabic posts
    if "egypt" in location.lower() or "مصر" in location:
        arabic_query = f'راتب {role} مصر 2025'
        results += search(arabic_query, max_results=5)

    return results


def search_trends(role: str, location: str) -> list[dict]:
    """
    Search for market trends and in-demand skills for a role.
    """
    queries = [
        f'most in demand skills {role} {location} 2025',
        f'{role} requirements hiring trends {location} 2025',
    ]

    results = []
    for q in queries:
        results += search(q, max_results=5)

    return results