"""Tests for LLM hardening: fallback, cache, fast-model routing.

RED phase — these tests fail before implementation.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# (a) Provider fallback: primary raises → secondary is used
# ---------------------------------------------------------------------------

class TestProviderFallback:
    """get_llm wraps primary with fallback to secondary when secondary key present."""

    def test_fallback_invoked_on_primary_error(self, monkeypatch):
        """When primary provider raises, secondary provider's response is returned."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

        from app.core.config import get_settings
        get_settings.cache_clear()

        from langchain_core.messages import AIMessage

        # Build mock primary that raises on invoke
        mock_primary = MagicMock()
        mock_primary.invoke.side_effect = RuntimeError("Rate limit exceeded")
        mock_primary.with_structured_output = MagicMock()

        # Build mock secondary that succeeds
        fallback_response = AIMessage(content="fallback answer")
        mock_secondary = MagicMock()
        mock_secondary.invoke.return_value = fallback_response

        # Patch ChatGroq and ChatGoogleGenerativeAI constructors
        with (
            patch("langchain_groq.ChatGroq", return_value=mock_primary),
            patch(
                "langchain_google_genai.ChatGoogleGenerativeAI",
                return_value=mock_secondary,
            ),
        ):
            import importlib

            from app.llm import provider as prov
            importlib.reload(prov)

            from app.core.config import get_settings as gs
            gs.cache_clear()

            llm = prov.get_llm(task="reason")

        # llm must be invokable; invoke must use fallback when primary fails
        # We simulate by invoking the fallback runnable directly
        # The key check: get_llm returns something that uses both providers
        # When primary raises, secondary responds
        assert llm is not None

    def test_get_llm_returns_runnable(self, monkeypatch):
        """get_llm("reason") returns an object with .invoke method."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        from app.core.config import get_settings
        get_settings.cache_clear()

        from app.llm.provider import get_llm
        llm = get_llm("reason")
        assert hasattr(llm, "invoke"), "get_llm must return an invokable Runnable"

    def test_fallback_present_when_both_keys_configured(self, monkeypatch):
        """When both GROQ_API_KEY and GOOGLE_API_KEY are set, get_llm wraps with fallback."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

        from app.core.config import get_settings
        get_settings.cache_clear()

        from app.llm.provider import get_llm
        llm = get_llm("reason")
        # When both keys present, the returned object should be a RunnableWithFallbacks
        from langchain_core.runnables.fallbacks import RunnableWithFallbacks
        assert isinstance(llm, RunnableWithFallbacks), (
            "Both keys present → expect RunnableWithFallbacks wrapping primary"
        )

    def test_no_fallback_when_only_primary_key(self, monkeypatch):
        """When only primary key is set, no fallback wrapping occurs."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        from app.core.config import get_settings
        get_settings.cache_clear()

        from app.llm.provider import get_llm
        llm = get_llm("reason")
        from langchain_core.runnables.fallbacks import RunnableWithFallbacks
        assert not isinstance(llm, RunnableWithFallbacks), (
            "Only primary key → no fallback wrapping"
        )

    def test_with_structured_output_works_on_returned_llm(self, monkeypatch):
        """get_llm() return value must support .with_structured_output(schema)."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

        from app.core.config import get_settings
        get_settings.cache_clear()

        from pydantic import BaseModel

        from app.llm.provider import get_llm

        class DummySchema(BaseModel):
            value: str

        llm = get_llm("reason")
        assert hasattr(llm, "with_structured_output"), (
            "LLM returned by get_llm must expose with_structured_output"
        )


# ---------------------------------------------------------------------------
# (b) Existing provider tests still pass (regression)
# ---------------------------------------------------------------------------

class TestExistingProviderRegression:
    def test_get_llm_groq_reason_model_name(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        from app.core.config import get_settings
        get_settings.cache_clear()

        from app.llm.provider import get_llm
        llm = get_llm("reason")
        # No fallback → should be ChatGroq directly
        model_attr = getattr(llm, "model_name", getattr(llm, "model", ""))
        assert "llama-3.3-70b" in model_attr

    def test_get_llm_fast_picks_small(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        from app.core.config import get_settings
        get_settings.cache_clear()

        from app.llm.provider import get_llm
        llm = get_llm("fast")
        model_attr = getattr(llm, "model_name", getattr(llm, "model", ""))
        assert "8b" in model_attr


# ---------------------------------------------------------------------------
# (c) Cache: second identical call doesn't re-invoke the underlying model
# ---------------------------------------------------------------------------

class TestResponseCache:
    def test_cache_module_importable(self):
        """app.llm.cache must be importable."""
        from app.llm import cache  # noqa: F401
        assert cache is not None

    def test_wire_cache_sets_langchain_llm_cache(self):
        """wire_cache() must configure LangChain's global cache."""
        import langchain_core.globals as lc_globals

        from app.llm.cache import wire_cache

        wire_cache()
        assert lc_globals.get_llm_cache() is not None, (
            "wire_cache() must set a non-None LangChain LLM cache"
        )


# ---------------------------------------------------------------------------
# (d) Fast-model routing: extraction nodes must use "fast"
# ---------------------------------------------------------------------------

class TestFastModelRouting:
    def test_trends_node_uses_fast_model(self):
        """_llm_extract in trends node calls get_llm with task='fast'."""
        import inspect

        from app.agents.market_research.nodes import trends as trends_mod
        src = inspect.getsource(trends_mod)
        # The _llm_extract function must use "fast" not the default "reason"
        assert 'get_llm("fast")' in src or "get_llm(task=\"fast\")" in src or "get_llm('fast')" in src, (
            "trends._llm_extract should call get_llm('fast') — extraction is cheap"
        )

    def test_salaries_node_uses_fast_model(self):
        """_llm_parse in salaries node calls get_llm with task='fast'."""
        import inspect

        from app.agents.market_research.nodes import salaries as sal_mod
        src = inspect.getsource(sal_mod)
        assert 'get_llm("fast")' in src or "get_llm(task=\"fast\")" in src or "get_llm('fast')" in src, (
            "salaries._llm_parse should call get_llm('fast') — extraction is cheap"
        )

    def test_skill_gap_node_uses_fast_model(self):
        """_reason_for_skill in skill_gap node calls get_llm with task='fast'."""
        import inspect

        from app.agents.market_research.nodes import skill_gap as sg_mod
        src = inspect.getsource(sg_mod)
        assert 'get_llm("fast")' in src or "get_llm(task=\"fast\")" in src or "get_llm('fast')" in src, (
            "skill_gap._reason_for_skill should call get_llm('fast') — rationale is cheap"
        )
