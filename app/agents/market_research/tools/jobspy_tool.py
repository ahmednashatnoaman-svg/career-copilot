"""JobSpy multi-source job search tool.

Searches LinkedIn, Indeed, Glassdoor, and ZipRecruiter via the
python-jobspy library (https://github.com/speedyapply/JobSpy).
Returns a normalised list of job dicts compatible with the rest of
the market-research pipeline.

Glassdoor insights (salary estimates, ratings) are included when
JobSpy returns them from the Glassdoor scrape.

Gracefully degrades to an empty list when python-jobspy is not
installed or when scraping fails.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_SITE_MAP = {
    "international": ["linkedin", "indeed", "glassdoor", "zip_recruiter"],
    "egypt": ["linkedin", "indeed"],
    "freelance": ["linkedin", "indeed"],
}


def search_jobs(
    role: str,
    location: str = "Remote",
    mode: str = "international",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search multiple job boards via JobSpy.

    Args:
        role: Job title / search query (e.g. "Senior Python Engineer").
        location: City, country, or "Remote".
        mode: One of "international", "egypt", "freelance".
        limit: Max results per site (total = limit × sites).

    Returns:
        List of normalised job dicts with keys:
        job_id, title, company, location, url, description,
        salary_min, salary_max, glassdoor_rating, source.
    """
    try:
        import jobspy  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("python-jobspy not installed — skipping multi-board search")
        return []

    sites = _SITE_MAP.get(mode, _SITE_MAP["international"])

    try:
        df = jobspy.scrape_jobs(
            site_name=sites,
            search_term=role,
            location=location,
            results_wanted=limit,
            hours_old=72,
            country_indeed="worldwide" if location.lower() == "remote" else None,
        )
    except Exception:  # noqa: BLE001
        logger.exception("JobSpy scrape_jobs failed for role=%s location=%s", role, location)
        return []

    results: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        job: dict[str, Any] = {
            "job_id": str(row.get("id", "")),
            "title": str(row.get("title", "")),
            "company": str(row.get("company", "")),
            "location": str(row.get("location", "")),
            "url": str(row.get("job_url", row.get("url", ""))),
            "description": str(row.get("description", ""))[:2000],
            "source": str(row.get("site", "jobspy")),
            "salary_min": _safe_float(row.get("min_amount")),
            "salary_max": _safe_float(row.get("max_amount")),
            "salary_currency": str(row.get("currency", "USD")),
            "glassdoor_rating": _safe_float(row.get("company_rating")),
            "glassdoor_reviews": _safe_int(row.get("company_num_reviews")),
            "date_posted": str(row.get("date_posted", "")),
            "job_type": str(row.get("job_type", "")),
            "is_remote": bool(row.get("is_remote", False)),
        }
        if job["title"] and job["company"]:
            results.append(job)

    logger.info("JobSpy returned %d results for role=%s", len(results), role)
    return results


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val not in (None, "", "nan") else None
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> int | None:
    try:
        return int(val) if val not in (None, "", "nan") else None
    except (TypeError, ValueError):
        return None
