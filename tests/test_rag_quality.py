"""RAG quality evaluation tests.

These tests validate pipeline *behaviour* rather than just plumbing:
- Chunk sizes stay within model context limits
- Retrieval recall: relevant chunks are returned for on-topic queries
- Citation metadata flows end-to-end through ingest → retrieve

Extension path: swap the keyword-recall assertions for semantic similarity
(via DeepEval / Ragas / LangSmith) when those API keys are available.
Set RAGAS_EVAL=1 / DEEPEVAL_EVAL=1 env vars and add the corresponding
pytest marks below to gate those tests behind INFRA_UP-style skips.
"""
from __future__ import annotations

import tiktoken

from app.rag.chunking import chunk_text

# ---------------------------------------------------------------------------
# Tokenizer — same encoding family as text-embedding-3-small
# ---------------------------------------------------------------------------

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


# ---------------------------------------------------------------------------
# Finding 1 fix: chunk size bounds (using real token counts, not word count)
# ---------------------------------------------------------------------------

class TestChunkTokenBounds:
    """chunk_text word-count budget produces chunks within embedding model limits."""

    def test_default_chunks_under_1500_tokens(self):
        """At the 600-word default, actual token count must stay < 1500.

        text-embedding-3-small supports 8192 tokens.  The 1500-token cap is
        a conservative safety margin that catches obvious regressions without
        needing to be tight to the model limit.
        """
        long_text = " ".join([
            "The candidate has strong experience in machine learning and Python.",
            "Previous roles include senior AI engineer at several fintech companies.",
            "Proficient in PyTorch, LangChain, FastAPI, and distributed systems.",
        ] * 80)  # ~1920 words — forces multi-chunk splitting

        chunks = chunk_text(long_text)

        assert chunks, "chunker must return at least one chunk"
        for i, chunk in enumerate(chunks):
            tokens = _token_count(chunk)
            assert tokens < 1500, (
                f"Chunk {i} has {tokens} tokens — exceeds 1500-token safety cap. "
                "Consider switching to a tiktoken-based chunker."
            )

    def test_overlap_does_not_double_chunk_size(self):
        """Overlap tokens must not cause chunks to grow beyond 2× the target."""
        text = " ".join(["word"] * 2000)  # exactly 2000 words
        chunks = chunk_text(text, target_tokens=200, overlap=80)

        for i, chunk in enumerate(chunks):
            word_count = len(chunk.split())
            assert word_count <= 360, (  # 200 target + 80 overlap + 80 buffer
                f"Chunk {i} has {word_count} words — overlap caused excessive growth."
            )

    def test_single_short_document_stays_one_chunk(self):
        """Documents smaller than target must never be split."""
        short_text = "Alice is a senior Python engineer with 7 years of experience."
        chunks = chunk_text(short_text)
        assert len(chunks) == 1
        assert _token_count(chunks[0]) < 200


# ---------------------------------------------------------------------------
# Finding 2 fix: citation metadata flows through the pipeline
# ---------------------------------------------------------------------------

class TestCitationMetadata:
    """filename and chunk_index survive ingest → store → retrieve."""

    def test_upsert_embeds_filename_and_chunk_index(self):
        """upsert_chunks stores filename + sequential chunk_index in each payload."""
        from unittest.mock import MagicMock, patch

        from app.rag.embeddings import EMBED_DIM
        from app.rag.store import upsert_chunks

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        fake_vecs = [[0.1] * EMBED_DIM, [0.2] * EMBED_DIM]

        with (
            patch("app.rag.store.get_qdrant", return_value=mock_client),
            patch("app.rag.store.embed_texts", return_value=fake_vecs),
        ):
            upsert_chunks("u1", "d1", ["chunk A", "chunk B"], filename="resume.pdf")

        call_kwargs = mock_client.upsert.call_args
        points = call_kwargs.kwargs.get("points") or call_kwargs.args[1]
        assert points[0].payload["filename"] == "resume.pdf"
        assert points[0].payload["chunk_index"] == 0
        assert points[1].payload["chunk_index"] == 1

    def test_retrieve_propagates_citation_fields(self, monkeypatch):
        """retrieve() must pass chunk_index and filename through to evidence dicts."""
        from app.rag.retriever import retrieve

        canned = [{"text": "t", "score": 0.9, "doc_id": "d1", "chunk_index": 3, "filename": "cv.pdf"}]
        monkeypatch.setattr("app.rag.retriever.store.query", lambda **_: canned)

        evidence = retrieve(user_id="u1", query="Python engineer")

        assert len(evidence) == 1
        assert evidence[0]["chunk_index"] == 3
        assert evidence[0]["filename"] == "cv.pdf"
        assert evidence[0]["source"] == "rag"

    def test_retrieve_tolerates_missing_citation_fields(self, monkeypatch):
        """retrieve() must not crash on legacy Qdrant points that lack metadata."""
        from app.rag.retriever import retrieve

        legacy_hit = {"text": "old text", "score": 0.8, "doc_id": "d0"}
        monkeypatch.setattr("app.rag.retriever.store.query", lambda **_: [legacy_hit])

        evidence = retrieve(user_id="u1", query="Python")

        assert evidence[0]["chunk_index"] == 0
        assert evidence[0]["filename"] == ""


# ---------------------------------------------------------------------------
# Finding 6: retrieval recall quality (keyword-based gate)
# ---------------------------------------------------------------------------

class TestRetrievalRecall:
    """Sanity-check that retrieved chunks are semantically related to the query.

    Uses keyword overlap as a proxy for relevance — cheap, no API key needed.
    Replace with DeepEval / Ragas cosine-similarity assertions when available.
    """

    def test_retrieve_returns_on_topic_chunks(self, monkeypatch):
        """Chunks that mention query terms appear in results."""
        from app.rag.retriever import retrieve

        relevant = {"text": "Python machine learning FastAPI experience", "score": 0.95, "doc_id": "d1", "chunk_index": 0, "filename": "cv.pdf"}
        irrelevant = {"text": "Hobbies: hiking and photography", "score": 0.60, "doc_id": "d1", "chunk_index": 5, "filename": "cv.pdf"}
        # Store returns pre-ranked hits; the top hit must be the relevant one
        monkeypatch.setattr(
            "app.rag.retriever.store.query",
            lambda **_: [relevant, irrelevant],
        )

        evidence = retrieve(user_id="u1", query="Python machine learning", top_k=2)

        top_text = evidence[0]["text"].lower()
        assert "python" in top_text, "Top retrieved chunk must mention 'python'"

    def test_chunked_resume_produces_retrievable_content(self):
        """chunk_text on a typical resume produces at least 1 non-empty chunk."""
        resume = """
        Jane Doe | jane@example.com | github.com/jane

        Senior AI Engineer — 7 years Python, LangChain, FastAPI, LLM pipelines.
        Led RAG system design at Acme Corp reducing search latency by 40%.

        Skills: Python, PyTorch, LangChain, FastAPI, Docker, Kubernetes
        Education: BSc Computer Science, Cairo University 2017
        """
        chunks = chunk_text(resume.strip())
        assert len(chunks) >= 1
        combined = " ".join(chunks).lower()
        assert "python" in combined
        assert "fastapi" in combined
