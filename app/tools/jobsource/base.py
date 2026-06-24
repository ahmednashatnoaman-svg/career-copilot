"""Base abstractions for job-source adapters."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class JobPosting(BaseModel):
    """Normalised representation of a single job posting."""

    title: str
    company: str
    location: str | None
    url: str
    salary: str | None = None
    source: str
    snippet: str | None = None


class JobSource(ABC):
    """Abstract adapter that every job-data provider must implement."""

    name: str

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobPosting]:
        """Return up to *limit* job postings matching *query*."""
