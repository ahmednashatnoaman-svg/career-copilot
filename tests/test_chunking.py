from app.rag.chunking import chunk_text


class TestChunkText:
    """Test suite for document chunking."""

    def test_small_text_single_chunk(self):
        """A small text (5 words) should yield exactly 1 chunk."""
        text = "This is a small text."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_large_text_multiple_chunks(self):
        """A 3000-word text should yield more than 1 chunk."""
        # Generate a 3000-word text
        words = ["word"] * 3000
        text = " ".join(words)
        chunks = chunk_text(text)
        assert len(chunks) > 1
        # All chunks should be non-empty
        assert all(len(chunk) > 0 for chunk in chunks)

    def test_consecutive_chunks_have_overlap(self):
        """Consecutive chunks should share overlap text."""
        # Create a medium-length text with clear paragraph boundaries
        paragraphs = [" ".join([f"word{i}"] * 100) for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, target_tokens=600, overlap=80)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Check overlap between consecutive chunks
        for i in range(len(chunks) - 1):
            curr_chunk = chunks[i]
            next_chunk = chunks[i + 1]

            # The end of current chunk should overlap with start of next chunk
            # (at least some common words due to overlap mechanism)
            curr_words = set(curr_chunk.split())
            next_words = set(next_chunk.split())
            overlap_words = curr_words & next_words
            assert len(overlap_words) > 0, f"No overlap between chunk {i} and {i+1}"

    def test_chunks_respect_target_tokens(self):
        """Each chunk should be <= target_tokens (with reasonable margin)."""
        text = "\n\n".join([" ".join(["word"] * 100) for _ in range(15)])
        chunks = chunk_text(text, target_tokens=600)

        # Each chunk token count (approximated by word count) should be reasonable
        for chunk in chunks:
            token_count = len(chunk.split())
            # Allow some overage due to paragraph/sentence boundary preservation
            assert token_count <= 700, f"Chunk too large: {token_count} tokens"

    def test_empty_text_returns_empty_list(self):
        """Empty text should return an empty list."""
        chunks = chunk_text("")
        assert chunks == []

    def test_whitespace_only_returns_empty_list(self):
        """Whitespace-only text should return an empty list."""
        chunks = chunk_text("   \n\n   \t  ")
        assert chunks == []

    def test_single_paragraph(self):
        """A single paragraph should be handled correctly."""
        text = "This is a single paragraph with some content."
        chunks = chunk_text(text)
        assert len(chunks) >= 1
        assert all(len(chunk) > 0 for chunk in chunks)

    def test_custom_parameters(self):
        """Custom target_tokens and overlap should be respected."""
        text = "\n\n".join([" ".join(["word"] * 50) for _ in range(10)])
        chunks = chunk_text(text, target_tokens=300, overlap=40)

        assert len(chunks) > 0
        assert all(len(chunk) > 0 for chunk in chunks)

        # Verify overlaps exist between consecutive chunks
        if len(chunks) > 1:
            for i in range(len(chunks) - 1):
                overlap_words = set(chunks[i].split()) & set(chunks[i + 1].split())
                assert len(overlap_words) > 0
