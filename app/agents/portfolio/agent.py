"""Portfolio analysis agent node using GitHub data."""

from typing import Any

from pydantic import BaseModel

from app.agents.portfolio.github_client import fetch_profile
from app.llm.provider import get_llm
from app.orchestrator.state import CopilotState


class PortfolioReport(BaseModel):
    """Portfolio analysis report with GitHub insights and LLM-generated analysis."""

    profile: dict[str, Any] | None = None
    top_projects: list[dict[str, Any]] = []
    languages: dict[str, int] = {}
    strengths: str | None = None
    gaps: str | None = None
    suggestions: str | None = None
    skipped: bool = False


async def portfolio_node(
    state: CopilotState,
    github_username: str | None = None,
    github_token: str | None = None,
) -> dict[str, PortfolioReport]:
    """Analyze user portfolio using GitHub profile data.

    Fetches GitHub profile and repositories, then uses LLM to generate
    strengths, gaps, and improvement suggestions.

    Args:
        state: LangGraph state containing user context.
        github_username: GitHub username (optional; sourced from state if not provided).
        github_token: GitHub token (optional; sourced from settings if not provided).

    Returns:
        Dict with key "portfolio" containing a PortfolioReport.
        If credentials are missing, returns a graceful "skipped" report.
    """
    # Fallback to extracting from state if not provided
    if github_username is None:
        github_username = state.get("github_username")
    if github_token is None:
        github_token = state.get("github_token")

    # Graceful handling of missing credentials
    if not github_username or not github_token:
        return {
            "portfolio": PortfolioReport(
                profile=None,
                top_projects=[],
                languages={},
                strengths=None,
                gaps=None,
                suggestions=None,
                skipped=True,
            )
        }

    # Fetch GitHub profile
    profile = await fetch_profile(github_username, github_token)

    # If fetch fails, return skipped report
    if profile is None:
        return {
            "portfolio": PortfolioReport(
                profile=None,
                top_projects=[],
                languages={},
                strengths=None,
                gaps=None,
                suggestions=None,
                skipped=True,
            )
        }

    # Extract top projects and languages from profile
    top_projects = profile.get("top_projects", [])
    languages = profile.get("languages", {})

    # Use LLM to generate strengths, gaps, and suggestions
    llm = get_llm(task="reason")

    # Build prompt for analysis
    projects_list = top_projects[:5]
    projects_summary = "\n".join(
        [
            f"- {p['name']} ({p.get('language', 'Unknown')}): {p.get('stars', 0)} stars"
            for p in projects_list
        ]
    )

    languages_summary = ", ".join([f"{lang} ({count})" for lang, count in languages.items()])

    analysis_prompt = f"""Analyze this GitHub portfolio and provide insights:

User: {profile.get('username', 'Unknown')}
Public Repos: {profile.get('repos', 0)}
Followers: {profile.get('followers', 0)}

Top Projects:
{projects_summary}

Languages Used: {languages_summary}

Provide your analysis in the following format:
STRENGTHS: [1-2 sentences on technical strengths]
GAPS: [1-2 sentences on skill gaps]
SUGGESTIONS: [1-2 sentences on improvement recommendations]

Be concise and specific based on the portfolio data."""

    response = llm.invoke(analysis_prompt)
    response_text = response.content if hasattr(response, "content") else str(response)

    # Parse LLM response
    strengths = None
    gaps = None
    suggestions = None

    for line in response_text.split("\n"):
        if line.startswith("STRENGTHS:"):
            strengths = line.replace("STRENGTHS:", "").strip()
        elif line.startswith("GAPS:"):
            gaps = line.replace("GAPS:", "").strip()
        elif line.startswith("SUGGESTIONS:"):
            suggestions = line.replace("SUGGESTIONS:", "").strip()

    return {
        "portfolio": PortfolioReport(
            profile=profile,
            top_projects=top_projects,
            languages=languages,
            strengths=strengths,
            gaps=gaps,
            suggestions=suggestions,
            skipped=False,
        )
    }
