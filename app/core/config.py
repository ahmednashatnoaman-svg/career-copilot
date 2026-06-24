from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Career Copilot"
    app_env: str = "development"

    # LLM
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_model_fast: str = "llama-3.1-8b-instant"
    groq_api_key: str | None = None
    google_api_key: str | None = None

    # tools
    tavily_api_key: str | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    github_token: str | None = None

    # datastores
    database_url: str = "postgresql://career:career@127.0.0.1:5433/career"
    qdrant_url: str = "http://127.0.0.1:6333"

    # tracing
    langchain_project: str = "career-copilot"


@lru_cache
def get_settings() -> Settings:
    return Settings()
