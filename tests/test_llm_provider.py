from app.core.config import get_settings
from app.llm.provider import get_llm


def test_get_llm_groq_reason(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    llm = get_llm("reason")
    assert llm is not None
    # langchain-groq exposes .model_name
    assert "llama-3.3-70b" in getattr(llm, "model_name", getattr(llm, "model", ""))


def test_get_llm_fast_picks_small(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    llm = get_llm("fast")
    assert "8b" in getattr(llm, "model_name", getattr(llm, "model", ""))
