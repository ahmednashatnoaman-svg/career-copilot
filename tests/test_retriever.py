"""Test suite for RAG retriever."""
from unittest.mock import MagicMock

from app.rag.retriever import retrieve


class TestRetrieve:
    """Test suite for the retrieve function."""

    def test_retrieve_wraps_store_query_into_evidence_dicts(self, monkeypatch):
        """retrieve() should wrap store.query results into evidence dicts with source="rag"."""
        # Arrange: mock store.query to return canned hits
        canned_hits = [
            {"text": "Hit 1 text", "score": 0.95, "doc_id": "doc_123"},
            {"text": "Hit 2 text", "score": 0.87, "doc_id": "doc_456"},
            {"text": "Hit 3 text", "score": 0.72, "doc_id": "doc_789"},
        ]

        mock_query = MagicMock(return_value=canned_hits)
        monkeypatch.setattr("app.rag.retriever.store.query", mock_query)

        # Act
        result = retrieve(user_id="user_001", query="test query", top_k=6)

        # Assert: store.query was called with correct params
        mock_query.assert_called_once_with(user_id="user_001", text="test query", top_k=6)

        # Assert: result is a list of 3 dicts
        assert len(result) == 3

        # Assert: each dict has text, score, doc_id, and source="rag"
        for i, evidence in enumerate(result):
            assert evidence["text"] == canned_hits[i]["text"]
            assert evidence["score"] == canned_hits[i]["score"]
            assert evidence["doc_id"] == canned_hits[i]["doc_id"]
            assert evidence["source"] == "rag"

    def test_retrieve_respects_top_k_parameter(self, monkeypatch):
        """retrieve() should pass top_k to store.query."""
        canned_hits = [{"text": "text", "score": 0.9, "doc_id": "doc_1"}]
        mock_query = MagicMock(return_value=canned_hits)
        monkeypatch.setattr("app.rag.retriever.store.query", mock_query)

        # Act with top_k=10
        retrieve(user_id="user_001", query="test", top_k=10)

        # Assert: top_k=10 was passed through
        mock_query.assert_called_once_with(
            user_id="user_001", text="test", top_k=10
        )

    def test_retrieve_empty_results(self, monkeypatch):
        """retrieve() should handle empty results gracefully."""
        mock_query = MagicMock(return_value=[])
        monkeypatch.setattr("app.rag.retriever.store.query", mock_query)

        result = retrieve(user_id="user_001", query="no results query")

        assert result == []
        assert isinstance(result, list)


class TestIngestDocument:
    """Test suite for the ingest_document function."""

    def test_ingest_document_plain_text_dispatches_correctly(self, monkeypatch):
        """ingest_document with plain text should chunk and upsert, returning chunk count."""
        from app.rag.ingest import ingest_document

        # Mock chunking and upserting
        mock_chunk_text = MagicMock(return_value=["chunk1", "chunk2", "chunk3"])
        mock_upsert_chunks = MagicMock(return_value=3)

        monkeypatch.setattr("app.rag.ingest.chunk_text", mock_chunk_text)
        monkeypatch.setattr("app.rag.ingest.upsert_chunks", mock_upsert_chunks)

        # Act
        result = ingest_document(
            user_id="user_001",
            doc_id="doc_001",
            text="This is test content to be chunked.",
        )

        # Assert: chunk_text was called on the text
        mock_chunk_text.assert_called_once_with(
            "This is test content to be chunked."
        )

        # Assert: upsert_chunks was called with user_id, doc_id, and chunks
        mock_upsert_chunks.assert_called_once_with(
            user_id="user_001", doc_id="doc_001", chunks=["chunk1", "chunk2", "chunk3"]
        )

        # Assert: returns the chunk count
        assert result == 3

    def test_ingest_document_empty_text_returns_zero(self, monkeypatch):
        """ingest_document with empty text should return 0."""
        from app.rag.ingest import ingest_document

        mock_chunk_text = MagicMock(return_value=[])
        mock_upsert_chunks = MagicMock(return_value=0)

        monkeypatch.setattr("app.rag.ingest.chunk_text", mock_chunk_text)
        monkeypatch.setattr("app.rag.ingest.upsert_chunks", mock_upsert_chunks)

        result = ingest_document(
            user_id="user_001", doc_id="doc_001", text=""
        )

        assert result == 0
        mock_upsert_chunks.assert_called_once_with(
            user_id="user_001", doc_id="doc_001", chunks=[]
        )
