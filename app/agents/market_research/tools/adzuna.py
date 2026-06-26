"""
tools/adzuna.py — Adzuna Job Search API
========================================

Adzuna has a free developer API — register at:
https://developer.adzuna.com/

Set these in your .env:
    ADZUNA_APP_ID=your_app_id
    ADZUNA_APP_KEY=your_app_key

Supported countries (pass as country code):
    gb, us, au, ca, de, fr, in, nl, nz, pl, ru, sg, za
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_BASE_URL     = "https://api.adzuna.com/v1/api/jobs"
_RESULTS_PAGE = 2
_DEFAULT_COUNTRY = "gb"   # fallback when location doesn't map to a country code

# Maps common location strings to Adzuna country codes
_LOCATION_TO_COUNTRY: dict[str, str] = {
    "uk": "gb", "united kingdom": "gb", "london": "gb",
    "us": "us", "united states": "us", "new york": "us",
    "canada": "ca", "toronto": "ca",
    "australia": "au", "sydney": "au",
    "germany": "de", "berlin": "de",
    "france": "fr", "paris": "fr",
    "india": "in", "bangalore": "in", "mumbai": "in",
    "singapore": "sg",
    "netherlands": "nl", "amsterdam": "nl",
}


def _resolve_country(location: str) -> str:
    """Map a location string to an Adzuna country code."""
    return _LOCATION_TO_COUNTRY.get(location.lower().strip(), _DEFAULT_COUNTRY)


def search_jobs(role: str, location: str = "") -> list[dict]:
    """
    Search Adzuna for job postings.

    Args:
        role    : job title / keywords e.g. "Backend Developer"
        location: city or country e.g. "London", "United States"

    Returns:
        list of dicts with keys:
            title, company, location, url, snippet, source
    """
    app_id  = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        logger.warning("[adzuna] ADZUNA_APP_ID or ADZUNA_APP_KEY not set — skipping")
        return []

    country = _resolve_country(location)
    url     = f"{_BASE_URL}/{country}/search/1"

    params = {
        "app_id":           app_id,
        "app_key":          app_key,
        "results_per_page": _RESULTS_PAGE,
        "what":             role,
        "content-type":     "application/json",
    }

    # Add location as a where filter if provided
    if location:
        params["where"] = location

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title":    item.get("title", ""),
                "company":  item.get("company", {}).get("display_name", ""),
                "location": item.get("location", {}).get("display_name", location),
                "url":      item.get("redirect_url", ""),
                "snippet":  item.get("description", ""),
                "source":   "adzuna",
            })

        logger.info(f"[adzuna] '{role}' in '{location}' → {len(results)} results")
        return results

    except requests.HTTPError as e:
        logger.warning(f"[adzuna] HTTP error for '{role}': {e}")
        return []
    except Exception as e:
        logger.warning(f"[adzuna] unexpected error for '{role}': {e}")
        return []