"""LLM provider factory with provider fallback.

Returns the primary ``BaseChatModel`` for single-provider setups, or a
``RunnableWithFallbacks`` when the secondary provider's API key is also
configured.  The ``RunnableWithFallbacks`` wrapper transparently delegates
``.with_structured_output()``, ``.invoke()``, and other Runnable methods to
the primary model and falls back to the secondary on any error (rate-limits,
network timeouts, etc.).

Retry
-----
Tenacity-style retries are applied at the *structured-output chain* level by
callers that need them (``chain.with_retry(...)``).  Applying ``with_retry``
directly to the *base* model would break ``.with_structured_output()`` because
``RunnableRetry`` does not delegate that method.  The fallback wrapper already
handles the most important free-tier risk (groq ↔ gemini provider switching),
so per-call retry is a secondary concern handled in individual nodes if needed.

Fast-model routing
------------------
``task="fast"``  → Llama 3.1 8B (groq) or gemini-2.0-flash (google) — for
                   routing / extraction / classification.
``task="reason"`` → Llama 3.3 70B (groq) or gemini-2.0-flash (google) — for
                    judgment / planning / critique.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.config import get_settings

Task = Literal["reason", "fast"]


def _build_groq(model: str, temperature: float, max_tokens: int | None) -> BaseChatModel:
    from langchain_groq import ChatGroq

    s = get_settings()
    kwargs: dict = {"model": model, "temperature": temperature, "api_key": s.groq_api_key}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatGroq(**kwargs)


def _build_google(task: Task, temperature: float, max_tokens: int | None) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    gmodel = "gemini-2.0-flash"
    kwargs: dict = {"model": gmodel, "temperature": temperature, "api_key": s.google_api_key}
    if max_tokens is not None:
        kwargs["max_output_tokens"] = max_tokens
    return ChatGoogleGenerativeAI(**kwargs)


def get_llm(
    task: Task = "reason",
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> BaseChatModel | Runnable:
    """Return a LangChain chat model for the given task tier.

    When both provider keys are present, wraps the primary model with a
    ``RunnableWithFallbacks`` so the secondary provider is used transparently
    on any primary error.  The returned object still exposes
    ``.with_structured_output()``, ``.invoke()``, etc.
    """
    s = get_settings()
    model_name = s.llm_model_fast if task == "fast" else s.llm_model

    if s.llm_provider == "groq":
        primary = _build_groq(model_name, temperature, max_tokens)
        if s.google_api_key:
            secondary = _build_google(task, temperature, max_tokens)
            return primary.with_fallbacks([secondary])
        return primary

    if s.llm_provider == "google":
        primary = _build_google(task, temperature, max_tokens)
        if s.groq_api_key:
            # groq model for fast task, otherwise the reason model
            groq_model = s.llm_model_fast if task == "fast" else s.llm_model
            secondary = _build_groq(groq_model, temperature, max_tokens)
            return primary.with_fallbacks([secondary])
        return primary

    raise ValueError(f"Unsupported LLM_PROVIDER: {s.llm_provider!r}")
