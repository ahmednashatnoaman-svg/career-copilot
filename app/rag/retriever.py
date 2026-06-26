"""Retriever wrapper for RAG store queries."""
from __future__ import annotations

from app.rag import store


def retrieve(user_id: str, query: str, top_k: int = 6) -> list[dict]:
    """Thin wrapper over store.query, returns evidence dicts with source="rag".

    Args:
        user_id: User identifier for isolation.
        query: Search query text.
        top_k: Maximum number of results to return.

    Returns:
        List of evidence dicts with keys: text, score, doc_id, source.
        source is always "rag" to distinguish from other evidence types.
    """
    hits = store.query(user_id=user_id, text=query, top_k=top_k)

    # Wrap each hit with source="rag"
    evidence = [
        {
            "text": hit["text"],
            "score": hit["score"],
            "doc_id": hit["doc_id"],
            "source": "rag",
        }
        for hit in hits
    ]

    return evidence
