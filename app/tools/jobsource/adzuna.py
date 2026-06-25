"""Adzuna job-search API adapter."""

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.tools.jobsource.base import JobPosting, JobSource

logger = logging.getLogger(__name__)

_ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"
_DEFAULT_COUNTRY = "gb"


class AdzunaSource(JobSource):
    """Fetch live job postings from the Adzuna REST API."""

    name = "adzuna"

    def __init__(self, app_id: str, app_key: str, country: str = _DEFAULT_COUNTRY) -> None:
        self._app_id = app_id
        self._app_key = app_key
        self._country = country

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobPosting]:
        """Return up to *limit* job postings from Adzuna for *query*."""
        raw = self._fetch(query, location=location, limit=limit)
        return [self._to_posting(item) for item in raw.get("results", [])]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _fetch(self, query: str, *, location: str | None, limit: int) -> dict:
        params: dict[str, str | int] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "results_per_page": limit,
            "what": query,
            "content-type": "application/json",
        }
        if location:
            params["where"] = location

        url = f"{_ADZUNA_BASE}/{self._country}/search/1"
        with httpx.Client(timeout=10) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _to_posting(item: dict) -> JobPosting:
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        if salary_min is not None and salary_max is not None:
            salary = f"{int(salary_min)}-{int(salary_max)}"
        elif salary_min is not None:
            salary = str(int(salary_min))
        elif salary_max is not None:
            salary = str(int(salary_max))
        else:
            salary = None

        return JobPosting(
            title=item.get("title", ""),
            company=item.get("company", {}).get("display_name", ""),
            location=item.get("location", {}).get("display_name"),
            url=item.get("redirect_url", ""),
            salary=salary,
            source="adzuna",
            snippet=item.get("description"),
        )
