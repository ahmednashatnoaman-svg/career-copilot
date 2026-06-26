"""Unit tests for app.rag.store — all I/O mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from qdrant_client.models import Distance, VectorParams

from app.rag.embeddings import EMBED_DIM  # single source of truth for vector size

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(collection_exists: bool = False) -> MagicMock:
    client = MagicMock()
    client.collection_exists.return_value = collection_exists
    return client


def _make_mock_search_result(
    text: str, score: float, doc_id: str, chunk_index: int = 0, filename: str = ""
) -> MagicMock:
    point = MagicMock()
    point.score = score
    point.payload = {
        "text": text,
        "doc_id": doc_id,
        "user_id": "u1",
        "chunk_index": chunk_index,
        "filename": filename,
    }
    return point


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

class TestEnsureCollection:
    def test_creates_collection_when_absent(self):
        mock_client = _make_mock_client(collection_exists=False)

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
        ):
            from app.rag.store import ensure_collection

            ensure_collection()

        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args
        # extract vectors_config from positional or keyword arg
        vectors_config = (
            call_kwargs.kwargs.get("vectors_config")
            or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs["vectors_config"]
        )
        assert isinstance(vectors_config, VectorParams)
        assert vectors_config.size == EMBED_DIM
        assert vectors_config.distance == Distance.COSINE

    def test_skips_create_when_collection_exists(self):
        mock_client = _make_mock_client(collection_exists=True)

        with patch("app.rag.store.get_qdrant", return_value=mock_client):
            from app.rag.store import ensure_collection

            ensure_collection()

        mock_client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------

class TestUpsertChunks:
    def test_returns_chunk_count(self):
        mock_client = _make_mock_client(collection_exists=True)
        chunks = ["chunk one", "chunk two", "chunk three"]
        fake_vectors = [[0.1] * EMBED_DIM, [0.2] * EMBED_DIM, [0.3] * EMBED_DIM]

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
            patch("app.rag.store.embed_texts", return_value=fake_vectors),
        ):
            from app.rag.store import upsert_chunks

            count = upsert_chunks("user1", "doc1", chunks)

        assert count == 3
        mock_client.upsert.assert_called_once()

    def test_upsert_payload_contains_required_fields(self):
        mock_client = _make_mock_client(collection_exists=True)
        chunks = ["hello world"]
        fake_vectors = [[0.5] * EMBED_DIM]

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
            patch("app.rag.store.embed_texts", return_value=fake_vectors),
        ):
            from app.rag.store import upsert_chunks

            upsert_chunks("user42", "doc99", chunks)

        call_kwargs = mock_client.upsert.call_args
        points = (
            call_kwargs.kwargs.get("points") or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs["points"]
        )
        assert len(points) == 1
        payload = points[0].payload
        assert payload["user_id"] == "user42"
        assert payload["doc_id"] == "doc99"
        assert payload["text"] == "hello world"
        assert payload["chunk_index"] == 0
        assert "filename" in payload


# ---------------------------------------------------------------------------
# query — must always pass Filter(must=[FieldCondition(key="user_id", ...)])
# ---------------------------------------------------------------------------

class TestQuery:
    def test_query_applies_user_id_filter(self):
        mock_client = _make_mock_client()
        fake_vectors = [[0.1] * EMBED_DIM]
        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
            patch("app.rag.store.embed_texts", return_value=fake_vectors),
        ):
            from app.rag.store import query

            query("alice", "find me a job", top_k=3)

        mock_client.query_points.assert_called_once()
        call_kwargs = mock_client.query_points.call_args
        query_filter = call_kwargs.kwargs.get("query_filter")
        assert query_filter is not None, "query_filter must be passed"

        # Must have at least one must condition on user_id
        must_conditions = query_filter.must
        assert must_conditions, "Filter.must must be non-empty"
        user_id_conditions = [
            c for c in must_conditions
            if hasattr(c, "key") and c.key == "user_id"
        ]
        assert user_id_conditions, "There must be a FieldCondition on 'user_id'"
        assert user_id_conditions[0].match.value == "alice"

    def test_query_returns_correct_shape(self):
        mock_client = _make_mock_client()
        fake_vectors = [[0.1] * EMBED_DIM]
        mock_response = MagicMock()
        mock_response.points = [
            _make_mock_search_result("chunk text", 0.95, "doc_abc", chunk_index=2, filename="resume.pdf"),
        ]
        mock_client.query_points.return_value = mock_response

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
            patch("app.rag.store.embed_texts", return_value=fake_vectors),
        ):
            from app.rag.store import query

            results = query("u1", "query text")

        assert len(results) == 1
        assert results[0]["text"] == "chunk text"
        assert results[0]["score"] == 0.95
        assert results[0]["doc_id"] == "doc_abc"
        assert results[0]["chunk_index"] == 2
        assert results[0]["filename"] == "resume.pdf"

    def test_query_uses_top_k(self):
        mock_client = _make_mock_client()
        fake_vectors = [[0.1] * EMBED_DIM]
        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
            patch("app.rag.store.embed_texts", return_value=fake_vectors),
        ):
            from app.rag.store import query

            query("u1", "text", top_k=10)

        call_kwargs = mock_client.query_points.call_args
        limit = call_kwargs.kwargs.get("limit")
        assert limit == 10
