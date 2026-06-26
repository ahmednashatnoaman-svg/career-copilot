"""Coaching-agent settings.

Extends the shared ``app.core.config.Settings`` with coaching-specific
fields so all agents share a single ``.env`` file while coaching code can
still reference ``Settings`` and ``get_settings`` from this module.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator

from app.core.config import Settings as _BaseSettings


class Settings(_BaseSettings):
    """Shared base settings plus coaching-specific overrides."""

    # Coaching-specific fields (not in the shared base)
    database_connect_timeout_seconds: int = 1

    groq_temperature: float = 0.25
    groq_max_tokens: int = 1600
    groq_timeout_seconds: float = 30.0
    groq_max_retries: int = 2

    router_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    rate_limit_requests_per_minute: int = Field(default=30, ge=1, le=600)

    embedding_provider: Literal["hash", "sentence_transformers"] = "hash"
    embedding_dimension: int = Field(default=384, ge=32, le=4096)
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "career-coaching-agent"
    langsmith_endpoint: str | None = None

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return value.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
