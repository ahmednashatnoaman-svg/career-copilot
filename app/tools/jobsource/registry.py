"""Job-source registry: builds the active source list and fan-out search."""

import logging

from app.core.config import get_settings
from app.tools.jobsource.base import JobPosting, JobSource
from app.tools.jobsource.tavily_jobs import TavilyJobsSource

logger = logging.getLogger(__name__)


def get_sources() -> list[JobSource]:
    """Return the list of enabled job sources based on configured credentials.

    Priority:
    - AdzunaSource when both ``adzuna_app_id`` and ``adzuna_app_key`` are set.
    - TavilyJobsSource as a fallback (or when Adzuna keys are absent).
    """
    settings = get_settings()
    sources: list[JobSource] = []

    if settings.adzuna_app_id and settings.adzuna_app_key:
        from app.tools.jobsource.adzuna import AdzunaSource

        sources.append(AdzunaSource(app_id=settings.adzuna_app_id, app_key=settings.adzuna_app_key))

    if not sources:
        # No primary source available — fall back to Tavily
        api_key = settings.tavily_api_key or ""
        sources.append(TavilyJobsSource(api_key=api_key))

    return sources


def search_all(
    query: str,
    *,
    location: str | None = None,
    limit: int = 20,
) -> list[JobPosting]:
    """Fan out *query* across all registered sources.

    Each source is called inside a try/except so that a single provider
    failure never crashes the caller.  If *all* sources fail or return
    empty results, a fresh TavilyJobsSource is used as a last-resort
    fallback.
    """
    sources = get_sources()
    all_results: list[JobPosting] = []
    any_success = False

    for source in sources:
        try:
            results = source.search(query, location=location, limit=limit)
            all_results.extend(results)
            any_success = True
        except Exception:
            logger.exception("JobSource '%s' failed — skipping", source.name)

    if not any_success or not all_results:
        logger.warning("All primary sources failed or returned empty; using Tavily fallback")
        settings = get_settings()
        fallback = TavilyJobsSource(api_key=settings.tavily_api_key or "")
        try:
            all_results = fallback.search(query, location=location, limit=limit)
        except Exception:
            logger.exception("Tavily fallback also failed")

    return all_results
