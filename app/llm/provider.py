"""LLM provider factory with multi-provider fallback chains.

Provider priority when all keys are configured:
  LLM_PROVIDER=groq  → Llama (Groq) → Gemini (Google)
  LLM_PROVIDER=google → Gemini → Llama (Groq)

Fast-model routing
------------------
task="fast"   → llm_model_fast (Groq) / google_model_fast (Google)
task="reason" → llm_model (Groq) / google_model (Google)

Default free-tier Gemini models
--------------------------------
google_model      = "gemini-2.0-flash"       — 15 RPM / 1500 RPD free tier
google_model_fast = "gemini-2.0-flash-lite"  — 30 RPM / 1500 RPD free tier (highest RPM)

Override via env vars GOOGLE_MODEL and GOOGLE_MODEL_FAST if newer models are available.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.config import get_settings

Task = Literal["reason", "fast"]


def _build_groq(model: str, temperature: float, max_tokens: int | None, api_key: str | None = None) -> BaseChatModel:
    from langchain_groq import ChatGroq

    s = get_settings()
    key = api_key or s.groq_api_key
    kwargs: dict = {"model": model, "temperature": temperature, "api_key": key}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatGroq(**kwargs)


def _build_google(model: str, temperature: float, max_tokens: int | None) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    kwargs: dict = {"model": model, "temperature": temperature, "api_key": s.google_api_key}
    if max_tokens is not None:
        kwargs["max_output_tokens"] = max_tokens
    return ChatGoogleGenerativeAI(**kwargs)


def get_llm(
    task: Task = "reason",
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> BaseChatModel | Runnable:
    """Return a LangChain chat model for the given task tier.

    Wraps the primary model with ``RunnableWithFallbacks`` when secondary provider
    keys are present.
    """
    s = get_settings()

    groq_model = s.llm_model_fast if task == "fast" else s.llm_model
    g_model = s.google_model_fast if task == "fast" else s.google_model

    fallbacks: list[BaseChatModel] = []

    groq_keys = [k for k in [s.groq_api_key, s.groq_api_key_1, s.groq_api_key_2, s.groq_api_key_3] if k]

    if s.llm_provider == "groq":
        if not groq_keys:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        
        primary = _build_groq(groq_model, temperature, max_tokens, api_key=groq_keys[0])
        for key in groq_keys[1:]:
            fallbacks.append(_build_groq(groq_model, temperature, max_tokens, api_key=key))
            
        if s.google_api_key:
            fallbacks.append(_build_google(g_model, temperature, max_tokens))

    elif s.llm_provider == "google":
        primary = _build_google(g_model, temperature, max_tokens)
        for key in groq_keys:
            fallbacks.append(_build_groq(groq_model, temperature, max_tokens, api_key=key))

    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {s.llm_provider!r}")

    return primary.with_fallbacks(fallbacks) if fallbacks else primary
