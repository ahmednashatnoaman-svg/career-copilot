"""GitHub REST client for fetching profile and repository data."""

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def fetch_profile(
    username: str | None, token: str | None
) -> dict[str, Any] | None:
    """Fetch GitHub profile and repository data for analysis.

    Args:
        username: GitHub username (required).
        token: GitHub personal access token (required).

    Returns:
        Dict with keys: username, repos, followers, top_projects, languages.
        Returns None if username or token is missing or on HTTP error.
    """
    if not username or not token:
        return None

    base_url = "https://api.github.com"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch user profile
            profile_resp = await client.get(f"{base_url}/users/{username}", headers=headers)
            profile_resp.raise_for_status()
            profile_data = profile_resp.json()

            # Fetch public repos (sorted by stars)
            repos_resp = await client.get(
                f"{base_url}/users/{username}/repos?sort=stars&per_page=100",
                headers=headers,
            )
            repos_resp.raise_for_status()
            repos_data = repos_resp.json()

            # Parse profile data
            username_out = profile_data.get("login", username)
            public_repos = profile_data.get("public_repos", 0)
            followers = profile_data.get("followers", 0)

            # Extract top projects (limit to 10)
            top_projects = []
            languages_count: dict[str, int] = {}

            for repo in repos_data[:10]:
                top_projects.append(
                    {
                        "name": repo.get("name", ""),
                        "description": repo.get("description", ""),
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language", "Unknown"),
                        "url": repo.get("html_url", ""),
                    }
                )
                lang = repo.get("language")
                if lang:
                    languages_count[lang] = languages_count.get(lang, 0) + 1

            return {
                "username": username_out,
                "repos": public_repos,
                "followers": followers,
                "top_projects": top_projects,
                "languages": languages_count,
            }

    except httpx.HTTPError:
        # Gracefully handle HTTP errors (e.g., 404, 401)
        return None
