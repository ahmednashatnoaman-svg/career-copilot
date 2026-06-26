"""RAG lookup tool for market research agent."""

from __future__ import annotations

from app.rag.retriever import retrieve as _retrieve


def retrieve(query: str, user_id: str = "") -> list[dict]:
    """Search the user's RAG store for documents relevant to *query*.

    Args:
        query: Natural-language search query.
        user_id: User identifier for per-user vector isolation.
                 Pass an empty string to skip RAG (returns empty list).

    Returns:
        List of ``{"text": str, "score": float, "doc_id": str, "source": "rag"}``
        dicts, ordered by descending relevance score.
    """
    if not user_id:
        return []
    return _retrieve(user_id=user_id, query=query)
