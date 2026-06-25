"""LinkedIn public-page job-discovery via Tavily web search."""

import logging

from app.tools.jobsource.base import JobPosting, JobSource

logger = logging.getLogger(__name__)


class LinkedInSource(JobSource):
    """Discover LinkedIn job postings via Tavily web search.

    Public pages via web search only — no authenticated scraping (ToS).
    """

    name = "linkedin"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self,
        query: str,
        *,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobPosting]:
        """Return job postings discovered via LinkedIn public pages + Tavily search."""
        from tavily import TavilyClient  # lazy import to avoid hard dep at module level

        search_query = f"site:linkedin.com/jobs {query}"
        if location:
            search_query += f" {location}"

        try:
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
                        company=_extract_linkedin_company(item),
                        location=location,
                        url=item.get("url", ""),
                        salary=None,
                        source="linkedin",
                        snippet=item.get("content"),
                    )
                )
            return results
        except Exception as e:
            logger.error(f"LinkedIn search failed: {e}")
            return []


def _extract_linkedin_company(item: dict) -> str:
    """Extract company name from LinkedIn job posting title.

    LinkedIn job titles often follow pattern: "Job Title at Company Name"
    """
    title: str = item.get("title", "Unknown")
    if " at " in title:
        parts = title.split(" at ")
        if len(parts) >= 2:
            # Extract company from "Job Title at Company Name"
            company = parts[-1].strip()
            return company
    return "Unknown"
