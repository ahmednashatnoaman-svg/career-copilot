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
    """Create the Qdrant collection if it does not yet exist (idempotent)."""
    client = get_qdrant()
    if not client.collection_exists(COLLECTION):
        try:
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            )
        except Exception:  # noqa: BLE001
            pass  # concurrent caller already created it


def upsert_chunks(
    user_id: str,
    doc_id: str,
    chunks: list[str],
    *,
    filename: str | None = None,
) -> int:
    """Embed *chunks* and upsert them into Qdrant.

    Each point carries ``{user_id, doc_id, text, chunk_index, filename}``
    so retrieval results can identify their source document and position.

    Returns:
        Number of points upserted.
    """
    if not chunks:
        return 0

    ensure_collection()
    vectors = embed_texts(chunks)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "user_id": user_id,
                "doc_id": doc_id,
                "text": text,
                "chunk_index": idx,
                "filename": filename or "",
            },
        )
        for idx, (text, vec) in enumerate(zip(chunks, vectors, strict=True))
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
    ensure_collection()
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
            "chunk_index": point.payload.get("chunk_index", 0),
            "filename": point.payload.get("filename", ""),
        }
        for point in response.points
    ]
