"""Qdrant vector store for RAG — per-user isolation via payload filter."""
from __future__ import annotations

import uuid

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.clients import get_qdrant
from app.rag.embeddings import EMBED_DIM, embed_texts

COLLECTION = "career_docs"


def ensure_collection() -> None:
    """Create the Qdrant collection if it does not yet exist."""
    client = get_qdrant()
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )


def upsert_chunks(user_id: str, doc_id: str, chunks: list[str]) -> int:
    """Embed *chunks* and upsert them into Qdrant.

    Each point carries ``{user_id, doc_id, text}`` in its payload.

    Returns:
        Number of points upserted.
    """
    if not chunks:
        return 0

    vectors = embed_texts(chunks)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={"user_id": user_id, "doc_id": doc_id, "text": text},
        )
        for text, vec in zip(chunks, vectors, strict=True)
    ]

    client = get_qdrant()
    client.upsert(collection_name=COLLECTION, points=points)
    return len(points)


def query(user_id: str, text: str, top_k: int = 6) -> list[dict]:
    """Semantic search restricted to *user_id*'s documents.

    Returns:
        List of ``{"text": str, "score": float, "doc_id": str}`` dicts,
        ordered by descending relevance score.
    """
    (query_vector,) = embed_texts([text])

    user_filter = Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id),
            )
        ]
    )

    client = get_qdrant()
    response = client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=user_filter,
        limit=top_k,
        with_payload=True,
    )

    return [
        {
            "text": point.payload["text"],
            "score": point.score,
            "doc_id": point.payload["doc_id"],
        }
        for point in response.points
    ]
