"""
Wuzzuf scraper.

Strategy:
  1. Use web_search.search_jobs(site="wuzzuf.net") to discover job URLs (fast, no blocking)
  2. Use scrape_job() to enrich individual postings with full description + requirements    
"""

import logging
import time

import requests
from bs4 import BeautifulSoup

from .web_search import search_jobs as ddgs_search

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

_SCRAPE_DELAY = 2.0   # seconds between scrape requests
_MAX_SCRAPE   = 2     # max individual job pages to scrape per search


def search_jobs(role: str, location: str) -> list[dict]:
    """
    Discover Wuzzuf job listings via DDGS, then enrich top results by scraping.

    Returns:
        list of dicts with keys:
            title, company, location, url, snippet, requirements, source
    """
    raw = ddgs_search(role=role, location=location, site="wuzzuf.net")

    if not raw:
        logger.warning(f"[wuzzuf] no DDGS results for '{role}' in '{location}'")
        return []

    results = []

    for i, item in enumerate(raw):
        url = item.get("url", "")

        # Only follow actual job posting URLs, not search/category pages
        if "/jobs/p/" not in url and "wuzzuf.net/jobs" not in url:
            # Keep snippet-only result — still useful for skill extraction
            results.append({
                "title":        item.get("title", ""),
                "company":      "",
                "location":     location,
                "url":          url,
                "snippet":      item.get("snippet", ""),
                "requirements": [],
                "source":       "wuzzuf",
            })
            continue

        # Scrape full details for actual job pages (up to _MAX_SCRAPE)
        if i < _MAX_SCRAPE:
            detail = scrape_job(url)
            if detail:
                results.append({**detail, "snippet": item.get("snippet", ""), "source": "wuzzuf"})
            else:
                # Scrape failed — fall back to snippet
                results.append({
                    "title":        item.get("title", ""),
                    "company":      "",
                    "location":     location,
                    "url":          url,
                    "snippet":      item.get("snippet", ""),
                    "requirements": [],
                    "source":       "wuzzuf",
                })
        else:
            results.append({
                "title":        item.get("title", ""),
                "company":      "",
                "location":     location,
                "url":          url,
                "snippet":      item.get("snippet", ""),
                "requirements": [],
                "source":       "wuzzuf",
            })

    logger.info(f"[wuzzuf] '{role}' in '{location}' → {len(results)} listings")
    return results


def scrape_job(url: str) -> dict | None:
    """
    Scrape a single Wuzzuf job posting page.

    Returns dict with: title, company, location, url, requirements
    Returns None if scraping fails.
    """
    try:
        time.sleep(_SCRAPE_DELAY)
        response = requests.get(url, headers=_HEADERS, timeout=10)

        if response.status_code != 200:
            logger.warning(f"[wuzzuf] scrape {url} → HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # --- Title ---
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # --- Company ---
        company = ""
        company_tag = soup.find("a", {"class": lambda c: c and "company" in c.lower()})
        if company_tag:
            company = company_tag.get_text(strip=True)

        # --- Location ---
        location = ""
        loc_tag = soup.find("span", {"class": lambda c: c and "location" in c.lower()})
        if loc_tag:
            location = loc_tag.get_text(strip=True)

        # --- Requirements (bullet points in job description) ---
        requirements = []
        desc_section = soup.find("section", {"class": lambda c: c and "description" in c.lower()})
        if desc_section:
            bullets = desc_section.find_all("li")
            requirements = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]

        return {
            "title":        title,
            "company":      company,
            "location":     location,
            "url":          url,
            "requirements": requirements,
        }

    except Exception as e:
        logger.warning(f"[wuzzuf] scrape failed for {url}: {e}")
        return None