"""Tavily web-search fallback adapter for job postings."""

import logging

from app.tools.jobsource.base import JobPosting, JobSource

logger = logging.getLogger(__name__)


class TavilyJobsSource(JobSource):
    """Use Tavily web search as a fallback job-discovery mechanism."""

    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self,
        query: str,
        *,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobPosting]:
        """Return job postings discovered via Tavily search."""
        from tavily import TavilyClient  # lazy import to avoid hard dep at module level

        search_query = f"{query} job opening"
        if location:
            search_query += f" {location}"

        client = TavilyClient(api_key=self._api_key)
        response = client.search(
            query=search_query,
            search_depth="basic",
            max_results=limit,
            include_answer=False,
        )

        results: list[JobPosting] = []
        for item in response.get("results", []):
            results.append(
                JobPosting(
                    title=item.get("title", "Unknown Title"),
                    company=_extract_company(item),
                    location=location,
                    url=item.get("url", ""),
                    salary=None,
                    source="tavily",
                    snippet=item.get("content"),
                )
            )
        return results


def _extract_company(item: dict) -> str:
    """Best-effort company name extraction from a Tavily result item."""
    url: str = item.get("url", "")
    if url:
        # e.g. https://jobs.lever.co/acmecorp/... → "acmecorp"
        try:
            from urllib.parse import urlparse

            host = urlparse(url).hostname or ""
            parts = host.split(".")
            # strip common job-board prefixes
            if len(parts) >= 2:
                return parts[-2].title()
        except Exception:
            pass
    return "Unknown"
