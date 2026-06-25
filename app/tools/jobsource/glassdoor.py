"""Glassdoor public-page job-discovery via Tavily web search."""

import logging
import re

from app.tools.jobsource.base import JobPosting, JobSource

logger = logging.getLogger(__name__)


class GlassdoorSource(JobSource):
    """Discover Glassdoor job postings via Tavily web search.

    Public pages via web search only — no authenticated scraping (ToS).
    Attempts to extract salary information from content when available.
    """

    name = "glassdoor"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self,
        query: str,
        *,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobPosting]:
        """Return job postings discovered via Glassdoor public pages + Tavily search."""
        from tavily import TavilyClient  # lazy import to avoid hard dep at module level

        search_query = f"site:glassdoor.com {query} salary reviews"
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
                salary = _extract_salary_from_content(item.get("content", ""))
                results.append(
                    JobPosting(
                        title=item.get("title", "Unknown Title"),
                        company=_extract_glassdoor_company(item),
                        location=location,
                        url=item.get("url", ""),
                        salary=salary,
                        source="glassdoor",
                        snippet=item.get("content"),
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Glassdoor search failed: {e}")
            return []


def _extract_glassdoor_company(item: dict) -> str:
    """Extract company name from Glassdoor job posting title.

    Glassdoor job titles often follow pattern: "Job Title at Company Name"
    """
    title: str = item.get("title", "Unknown")
    if " at " in title:
        parts = title.split(" at ")
        if len(parts) >= 2:
            # Extract company from "Job Title at Company Name"
            company = parts[-1].strip()
            return company
    return "Unknown"


def _extract_salary_from_content(content: str) -> str | None:
    """Extract salary range from Glassdoor job posting content.

    Looks for patterns like "$150,000 - $180,000" or similar.
    """
    if not content:
        return None

    # Pattern: "$XXX,XXX - $XXX,XXX" or "$XXX,XXX - XXX,XXX"
    salary_pattern = r"\$[\d,]+\s*(?:-|to)\s*\$?[\d,]+"
    matches = re.findall(salary_pattern, content)

    if matches:
        # Return the first match found
        return matches[0]

    return None
