import os

from app.core.config import get_settings


def configure_tracing() -> None:
    """Idempotently set LangSmith env vars from settings."""
    s = get_settings()
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", s.langchain_project)
    # LANGCHAIN_API_KEY is read from the environment / .env by langsmith directly.
