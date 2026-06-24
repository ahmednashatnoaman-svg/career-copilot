"""Unit tests for portfolio/GitHub analysis agent node."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.portfolio.agent import PortfolioReport, portfolio_node
from app.agents.portfolio.github_client import fetch_profile
from app.orchestrator.state import CopilotState

# --- Mocked GitHub REST Response ---
SAMPLE_GITHUB_PROFILE_RESPONSE = {
    "login": "alice",
    "public_repos": 25,
    "followers": 150,
    "public_gists": 10,
    "repos_url": "https://api.github.com/users/alice/repos",
}

SAMPLE_REPOS_RESPONSE = [
    {
        "name": "awesome-project",
        "description": "A great Python tool",
        "stargazers_count": 450,
        "language": "Python",
        "url": "https://github.com/alice/awesome-project",
    },
    {
        "name": "webframework",
        "description": "A TypeScript web framework",
        "stargazers_count": 120,
        "language": "TypeScript",
        "url": "https://github.com/alice/webframework",
    },
    {
        "name": "data-processor",
        "description": "A Rust data processing library",
        "stargazers_count": 85,
        "language": "Rust",
        "url": "https://github.com/alice/data-processor",
    },
]


@pytest.mark.asyncio
async def test_github_client_fetch_profile_success():
    """Test fetch_profile parses canned GitHub REST JSON correctly."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        # Mock profile request
        profile_response = MagicMock()
        profile_response.json.return_value = SAMPLE_GITHUB_PROFILE_RESPONSE

        # Mock repos request
        repos_response = MagicMock()
        repos_response.json.return_value = SAMPLE_REPOS_RESPONSE

        mock_client.get.side_effect = [profile_response, repos_response]

        # Call fetch_profile
        result = await fetch_profile("alice", "fake_token")

        # Assertions
        assert result is not None
        assert result["username"] == "alice"
        assert result["repos"] == 25
        assert result["followers"] == 150
        assert len(result["top_projects"]) == 3
        assert result["top_projects"][0]["name"] == "awesome-project"
        assert result["top_projects"][0]["stars"] == 450
        assert "languages" in result
        assert "Python" in result["languages"]


@pytest.mark.asyncio
async def test_github_client_fetch_profile_missing_token():
    """Test fetch_profile gracefully handles missing token."""
    result = await fetch_profile("alice", None)
    assert result is None


@pytest.mark.asyncio
async def test_github_client_fetch_profile_missing_username():
    """Test fetch_profile gracefully handles missing username."""
    result = await fetch_profile(None, "fake_token")
    assert result is None


@pytest.mark.asyncio
async def test_portfolio_node_success():
    """Test portfolio_node returns PortfolioReport with mocked client and LLM."""
    mock_profile = {
        "username": "alice",
        "repos": 25,
        "followers": 150,
        "top_projects": [
            {"name": "awesome-project", "stars": 450, "language": "Python"},
        ],
        "languages": {"Python": 12, "TypeScript": 8, "Rust": 3},
    }

    # Create state with GitHub username
    state: CopilotState = {
        "user_id": "user123",
        "thread_id": "thread456",
        "user_message": "Analyze my portfolio",
    }

    with patch(
        "app.agents.portfolio.agent.fetch_profile",
        new_callable=AsyncMock,
        return_value=mock_profile,
    ), patch("app.agents.portfolio.agent.get_llm") as mock_get_llm:
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Mock LLM invoke to return a response with proper format
        mock_response_text = (
            "STRENGTHS: Alice is an experienced backend engineer.\n"
            "GAPS: Limited experience with frontend technologies.\n"
            "SUGGESTIONS: Learn modern frontend frameworks."
        )
        mock_llm.invoke.return_value = MagicMock(content=mock_response_text)

        # Call portfolio_node
        result = await portfolio_node(state, github_username="alice", github_token="fake_token")

        # Assertions
        assert "portfolio" in result
        portfolio: PortfolioReport = result["portfolio"]
        assert portfolio.profile["username"] == "alice"
        assert len(portfolio.top_projects) > 0
        assert portfolio.strengths is not None
        assert portfolio.gaps is not None
        assert portfolio.suggestions is not None


@pytest.mark.asyncio
async def test_portfolio_node_missing_credentials():
    """Test portfolio_node gracefully handles missing GitHub credentials."""
    state: CopilotState = {
        "user_id": "user123",
        "thread_id": "thread456",
        "user_message": "Analyze my portfolio",
    }

    # Call without credentials
    result = await portfolio_node(state, github_username=None, github_token=None)

    # Assertions: should have a graceful "skipped" report
    assert "portfolio" in result
    portfolio: PortfolioReport = result["portfolio"]
    assert portfolio.profile is None
    assert portfolio.skipped is True


def test_portfolio_report_schema():
    """Test PortfolioReport Pydantic schema validates correctly."""
    # Valid report
    report = PortfolioReport(
        profile={"username": "alice", "repos": 25, "followers": 150},
        top_projects=[
            {"name": "project1", "stars": 100, "language": "Python"},
        ],
        languages={"Python": 10},
        strengths="Experienced backend engineer",
        gaps="Needs frontend skills",
        suggestions="Learn React",
        skipped=False,
    )
    assert report.profile["username"] == "alice"
    assert not report.skipped

    # Skipped report
    skipped_report = PortfolioReport(
        profile=None,
        top_projects=[],
        languages={},
        strengths=None,
        gaps=None,
        suggestions=None,
        skipped=True,
    )
    assert skipped_report.skipped
    assert skipped_report.profile is None
