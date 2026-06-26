from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Career Copilot"
    app_env: str = "development"

    # LLM
    llm_provider: str = "groq"
    # Groq / generic model names (used as primary when llm_provider=groq)
    llm_model: str = "llama-3.3-70b-versatile"
    llm_model_fast: str = "llama-3.1-8b-instant"
    groq_api_key: str | None = None
    # Google Gemini model names (used as primary when llm_provider=google, else as fallback)
    # gemini-2.0-flash / gemini-2.0-flash-lite are deprecated as of 2026.
    # gemini-3.5-flash = current flagship; gemini-3.1-flash-lite = most cost-efficient.
    # Override via GOOGLE_MODEL / GOOGLE_MODEL_FAST env vars.
    google_model: str = "gemini-3.5-flash"
    google_model_fast: str = "gemini-3.1-flash-lite"
    google_api_key: str | None = None

    # Azure OpenAI (AI Foundry endpoint — OpenAI-compatible)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment_name: str = "gpt-4.1-mini"
    azure_openai_embedding_endpoint: str | None = None
    azure_openai_embedding_api_key: str | None = None
    azure_openai_embedding_deployment_name: str = "text-embedding-3-small"

    # tools
    tavily_api_key: str | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    github_token: str | None = None

    # datastores
    database_url: str = "postgresql://career:career@127.0.0.1:5433/career"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None

    # Supabase
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    # deployment
    render_external_url: str | None = None
    frontend_url: str = ""

    # tracing
    langchain_project: str = "career-copilot"


@lru_cache
def get_settings() -> Settings:
    return Settings()
