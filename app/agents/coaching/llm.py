"""Coaching LLM service backed by the shared ``app.llm.provider.get_llm`` router."""
from __future__ import annotations

import copy
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.coaching.settings import Settings
from app.llm.provider import get_llm


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_error: str | None = None
        self.fallback_count = 0
        # Lazily check if we have a key; get_llm itself is lazy
        self._configured: bool = bool(settings.groq_api_key)

    @property
    def configured(self) -> bool:
        return self._configured

    def clear_error(self) -> None:
        self.last_error = None

    def _get_chat(self):
        """Return a chat model via the shared provider router."""
        return get_llm("reason", temperature=self.settings.groq_temperature)

    def text(self, system: str, user: str, fallback: str) -> str:
        if not self._configured:
            self._mark_fallback("Groq API key is not configured.")
            return fallback

        try:
            chat = self._get_chat()
            result = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            self.last_error = None
        except Exception as exc:
            self._mark_fallback(f"{type(exc).__name__}: {exc}")
            return fallback

        content = getattr(result, "content", "")
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return str(content).strip() or fallback

    def json(
        self,
        system: str,
        user: str,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._configured:
            self._mark_fallback("Groq API key is not configured.")
            return copy.deepcopy(fallback)

        raw = self.text(system, user, json.dumps(fallback))
        parsed = extract_json_object(raw)
        if parsed is None:
            self._mark_fallback("LLM response was not valid JSON.")
            return copy.deepcopy(fallback)
        return parsed

    def _mark_fallback(self, reason: str) -> None:
        self.last_error = reason
        self.fallback_count += 1


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
