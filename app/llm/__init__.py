from app.llm.cache import wire_cache
from app.llm.provider import get_llm

# Wire the LangChain LLM cache on first import so repeated identical prompts
# at temperature=0 are served from cache without re-hitting the provider API.
wire_cache()

__all__ = ["get_llm", "wire_cache"]
