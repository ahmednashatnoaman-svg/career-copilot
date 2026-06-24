from typing import Literal

from langchain_core.language_models import BaseChatModel

from app.core.config import get_settings

Task = Literal["reason", "fast"]


def get_llm(task: Task = "reason", temperature: float = 0.0, max_tokens: int | None = None) -> BaseChatModel:
    s = get_settings()
    model = s.llm_model_fast if task == "fast" else s.llm_model

    if s.llm_provider == "groq":
        from langchain_groq import ChatGroq
        kwargs = {"model": model, "temperature": temperature, "api_key": s.groq_api_key}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ChatGroq(**kwargs)

    if s.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        gmodel = "gemini-2.0-flash" if task == "fast" else "gemini-2.0-flash"
        kwargs = {"model": gmodel, "temperature": temperature, "api_key": s.google_api_key}
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    raise ValueError(f"Unsupported LLM_PROVIDER: {s.llm_provider!r}")
