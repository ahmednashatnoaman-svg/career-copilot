"""
tools/upwork.py — Upwork Job Search
=====================================

Upwork has an official API but requires OAuth2 approval.
Apply for access at: https://www.upwork.com/developer/keys/apply

Set these in your .env:
    UPWORK_CLIENT_ID=your_client_id
    UPWORK_CLIENT_SECRET=your_client_secret
    UPWORK_ACCESS_TOKEN=your_access_token   (after OAuth flow)

IMPORTANT: Upwork API access requires application approval.
While waiting for approval, this falls back to web_search
with site:upwork.com so the node still returns results.
"""

from __future__ import annotations

import logging
import os

import requests

from .web_search import search_jobs as web_search_jobs

logger = logging.getLogger(__name__)

_API_BASE = "https://www.upwork.com/api/profiles/v2"


def _has_credentials() -> bool:
    return bool(
        os.getenv("UPWORK_CLIENT_ID")
        and os.getenv("UPWORK_CLIENT_SECRET")
        and os.getenv("UPWORK_ACCESS_TOKEN")
    )


def _search_via_api(query: str) -> list[dict]:
    """
    Search Upwork jobs via official API (requires approved access token).
    """
    token = os.getenv("UPWORK_ACCESS_TOKEN")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    params = {
        "q":       query,
        "paging":  "0;2",
        "sort":    "recency",
    }

    try:
        response = requests.get(
            f"{_API_BASE}/jobs/search",
            headers = headers,
            params  = params,
            timeout = 10,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("jobs", {}).get("job", []):
            results.append({
                "title":    item.get("title", ""),
                "company":  "Upwork Client",   # clients are anonymous on Upwork
                "location": item.get("client", {}).get("country", ""),
                "url":      f"https://www.upwork.com/jobs/{item.get('id', '')}",
                "snippet":  item.get("snippet", ""),
                "source":   "upwork",
            })

        logger.info(f"[upwork] API '{query}' → {len(results)} results")
        return results

    except requests.HTTPError as e:
        logger.warning(f"[upwork] API HTTP error: {e}")
        return []
    except Exception as e:
        logger.warning(f"[upwork] API error: {e}")
        return []


def _search_via_web(query: str) -> list[dict]:
    """
    Fallback: search Upwork listings via DuckDuckGo site: filter.
    Used when API credentials are not configured yet.
    """
    logger.info("[upwork] API credentials not set — falling back to web search")
    raw = web_search_jobs(role=query, location="", site="upwork.com")

    results = []
    for item in raw:
        results.append({
            "title":    item.get("title", ""),
            "company":  "Upwork Client",
            "location": "",
            "url":      item.get("url", ""),
            "snippet":  item.get("snippet", ""),
            "source":   "upwork",
        })

    return results


def search_jobs(query: str) -> list[dict]:
    """
    Search Upwork for freelance jobs.

    Uses official API if credentials are configured,
    falls back to web search otherwise.

    Args:
        query: role + optional keywords e.g. "Python Backend Developer"

    Returns:
        list of dicts with keys:
            title, company, location, url, snippet, source
    """
    if _has_credentials():
        results = _search_via_api(query)
        # If API returns nothing (e.g. rate limit), fall back to web
        if not results:
            results = _search_via_web(query)
        return results

    return _search_via_web(query)