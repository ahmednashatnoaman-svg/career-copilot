"""Tests for JobSource adapter: Adzuna, Tavily fallback, registry, and graceful degradation."""

from unittest.mock import MagicMock, patch

import httpx

from app.tools.jobsource.adzuna import AdzunaSource
from app.tools.jobsource.base import JobPosting, JobSource
from app.tools.jobsource.registry import get_sources, search_all

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

ADZUNA_CANNED_RESPONSE = {
    "results": [
        {
            "title": "Senior Python Engineer",
            "company": {"display_name": "Acme Corp"},
            "location": {"display_name": "London, UK"},
            "redirect_url": "https://www.adzuna.co.uk/jobs/details/123",
            "salary_min": 70000,
            "salary_max": 90000,
            "description": "We are looking for a Senior Python Engineer to join our platform team.",
        },
        {
            "title": "Backend Developer",
            "company": {"display_name": "Beta Ltd"},
            "location": {"display_name": "Remote"},
            "redirect_url": "https://www.adzuna.co.uk/jobs/details/456",
            # no salary fields
            "description": "Build and maintain REST APIs using Django and FastAPI.",
        },
    ]
}


# ---------------------------------------------------------------------------
# Test 1: AdzunaSource parses a canned API response into JobPosting[]
# ---------------------------------------------------------------------------


def test_adzuna_parses_canned_response():
    """AdzunaSource.search() correctly maps Adzuna JSON to JobPosting objects."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = ADZUNA_CANNED_RESPONSE
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        source = AdzunaSource(app_id="test-id", app_key="test-key")
        results = source.search("python engineer", location="London", limit=10)

    assert len(results) == 2

    # Verify first posting — shape matters
    first = results[0]
    assert isinstance(first, JobPosting)
    assert first.title == "Senior Python Engineer"
    assert first.company == "Acme Corp"
    assert first.location == "London, UK"
    assert first.url == "https://www.adzuna.co.uk/jobs/details/123"
    assert first.source == "adzuna"
    assert "70000" in first.salary or "90000" in first.salary  # salary rendered
    assert "Python" in first.snippet

    # Verify second posting — no salary → None
    second = results[1]
    assert second.title == "Backend Developer"
    assert second.company == "Beta Ltd"
    assert second.salary is None
    assert second.source == "adzuna"


def test_adzuna_name():
    """AdzunaSource.name is 'adzuna'."""
    source = AdzunaSource(app_id="x", app_key="y")
    assert source.name == "adzuna"


def test_adzuna_is_job_source():
    """AdzunaSource is a subclass of JobSource."""
    source = AdzunaSource(app_id="x", app_key="y")
    assert isinstance(source, JobSource)


# ---------------------------------------------------------------------------
# Test 2: search_all graceful degradation — one source fails, others continue
# ---------------------------------------------------------------------------


def test_search_all_degrades_gracefully_when_one_source_fails():
    """search_all() skips a failing source and returns results from healthy ones."""
    good_posting = JobPosting(
        title="Data Engineer",
        company="Good Corp",
        location="Berlin",
        url="https://example.com/job/1",
        source="mock_good",
        snippet="Great role at a good company.",
    )

    good_source = MagicMock(spec=JobSource)
    good_source.name = "mock_good"
    good_source.search.return_value = [good_posting]

    bad_source = MagicMock(spec=JobSource)
    bad_source.name = "mock_bad"
    bad_source.search.side_effect = RuntimeError("API key expired")

    with patch("app.tools.jobsource.registry.get_sources", return_value=[bad_source, good_source]):
        results = search_all("data engineer", location="Berlin", limit=5)

    assert len(results) == 1
    assert results[0].title == "Data Engineer"
    assert results[0].company == "Good Corp"
    assert results[0].source == "mock_good"


def test_search_all_falls_back_to_tavily_when_all_fail():
    """search_all() invokes Tavily fallback when ALL primary sources fail."""
    failing_source = MagicMock(spec=JobSource)
    failing_source.name = "mock_fail"
    failing_source.search.side_effect = RuntimeError("network error")

    tavily_posting = JobPosting(
        title="ML Engineer",
        company="AI Startup",
        location="Remote",
        url="https://jobs.example.com/ml-engineer",
        source="tavily",
        snippet="Exciting ML role at an AI startup.",
    )

    mock_tavily = MagicMock(spec=JobSource)
    mock_tavily.name = "tavily"
    mock_tavily.search.return_value = [tavily_posting]

    with (
        patch("app.tools.jobsource.registry.get_sources", return_value=[failing_source]),
        patch("app.tools.jobsource.registry.TavilyJobsSource", return_value=mock_tavily),
    ):
        results = search_all("ml engineer", location="Remote", limit=5)

    assert len(results) == 1
    assert results[0].source == "tavily"
    assert results[0].title == "ML Engineer"


# ---------------------------------------------------------------------------
# Test 3: get_sources() falls back to Tavily when Adzuna keys are absent
# ---------------------------------------------------------------------------


def test_get_sources_returns_adzuna_when_keys_present():
    """get_sources() includes AdzunaSource when both Adzuna keys are configured."""
    from app.core.config import Settings

    mock_settings = Settings.model_construct(
        adzuna_app_id="my-id",
        adzuna_app_key="my-key",
        tavily_api_key=None,
    )
    with patch("app.tools.jobsource.registry.get_settings", return_value=mock_settings):
        sources = get_sources()

    names = [s.name for s in sources]
    assert "adzuna" in names


def test_get_sources_falls_back_to_tavily_when_no_adzuna_keys():
    """get_sources() returns TavilyJobsSource when Adzuna keys are absent."""
    from app.core.config import Settings

    mock_settings = Settings.model_construct(
        adzuna_app_id=None,
        adzuna_app_key=None,
        tavily_api_key="tvly-test-key",
    )
    with patch("app.tools.jobsource.registry.get_settings", return_value=mock_settings):
        sources = get_sources()

    names = [s.name for s in sources]
    assert "tavily" in names
    assert "adzuna" not in names


def test_get_sources_returns_list_of_job_sources():
    """get_sources() always returns instances of JobSource."""
    from app.core.config import Settings

    mock_settings = Settings.model_construct(
        adzuna_app_id=None,
        adzuna_app_key=None,
        tavily_api_key="tvly-x",
    )
    with patch("app.tools.jobsource.registry.get_settings", return_value=mock_settings):
        sources = get_sources()

    assert len(sources) > 0
    for s in sources:
        assert isinstance(s, JobSource)
