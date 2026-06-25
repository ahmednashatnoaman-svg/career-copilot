from app.core.config import get_settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_provider == "groq"
    assert s.llm_model_fast  # has a default
    assert s.qdrant_url.startswith("http")
    assert s.database_url.endswith("/db")
