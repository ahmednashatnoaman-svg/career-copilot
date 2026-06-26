"""Document chunking for RAG pipeline."""


def chunk_text(
    text: str, *, target_tokens: int = 600, overlap: int = 80
) -> list[str]:
    """
    Chunk text recursively on paragraph and sentence boundaries.

    Args:
        text: Input text to chunk
        target_tokens: Target number of tokens per chunk (approximate, via word count)
        overlap: Number of tokens to overlap between consecutive chunks

    Returns:
        List of text chunks. Returns empty list if input is empty/whitespace-only.
        Each non-empty input returns at least 1 chunk.
    """
    # Handle empty or whitespace-only input
    text = text.strip()
    if not text:
        return []

    text_tokens = len(text.split())

    # If entire text is smaller than target, return as single chunk
    if text_tokens <= target_tokens:
        return [text]

    # Split on paragraph boundaries first
    paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return [text]

    # Pack paragraphs into chunks respecting target size with overlap
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = len(para.split())

        # If single paragraph exceeds target, split on sentence boundaries
        if para_tokens > target_tokens and current_chunk:
            # Save current chunk before handling large paragraph
            chunk_text_str = "\n\n".join(current_chunk)
            chunks.append(chunk_text_str)
            current_chunk = []
            current_tokens = 0

            # Split large paragraph into sentences
            sentences = _split_sentences(para)
            _pack_sentences_into_chunks(
                sentences, chunks, target_tokens, overlap
            )
        elif para_tokens > target_tokens and not current_chunk:
            # Large paragraph with no current chunk
            sentences = _split_sentences(para)
            _pack_sentences_into_chunks(
                sentences, chunks, target_tokens, overlap
            )
        else:
            # Small paragraph, add to current chunk
            if current_tokens + para_tokens <= target_tokens:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Current chunk is full, save it and start new one
                if current_chunk:
                    chunk_text_str = "\n\n".join(current_chunk)
                    chunks.append(chunk_text_str)

                # Start new chunk with overlap from previous if possible
                if chunks and overlap > 0:
                    last_chunk = chunks[-1]
                    overlap_text = _get_overlap(last_chunk, overlap)
                    current_chunk = [overlap_text, para] if overlap_text else [para]
                    current_tokens = len("\n\n".join(current_chunk).split())
                else:
                    current_chunk = [para]
                    current_tokens = para_tokens

    # Add remaining chunk
    if current_chunk:
        chunk_text_str = "\n\n".join(current_chunk)
        chunks.append(chunk_text_str)

    # Ensure we never return empty list for non-empty input
    return chunks if chunks else [text]


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries, falling back to word splits."""
    # Simple sentence splitting on common terminators
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    # If no sentence boundaries found, split into chunks of ~50 words
    if len(sentences) == 1:
        words = text.split()
        sentences = []
        for i in range(0, len(words), 50):
            sentences.append(" ".join(words[i : i + 50]))

    return sentences


def _pack_sentences_into_chunks(
    sentences: list[str],
    chunks: list[str],
    target_tokens: int,
    overlap: int,
) -> None:
    """Pack sentences into chunks with overlap."""
    current_chunk: list[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = len(sent.split())

        if current_tokens + sent_tokens <= target_tokens:
            current_chunk.append(sent)
            current_tokens += sent_tokens
        else:
            if current_chunk:
                chunk_text_str = " ".join(current_chunk)
                chunks.append(chunk_text_str)

                # Add overlap from previous chunk
                if overlap > 0:
                    overlap_text = _get_overlap(chunk_text_str, overlap)
                    current_chunk = (
                        [overlap_text, sent] if overlap_text else [sent]
                    )
                    current_tokens = len(" ".join(current_chunk).split())
                else:
                    current_chunk = [sent]
                    current_tokens = sent_tokens
            else:
                # Single sentence exceeds target; include it anyway
                chunks.append(sent)
                current_chunk = []
                current_tokens = 0

    if current_chunk:
        chunk_text_str = " ".join(current_chunk)
        chunks.append(chunk_text_str)


def _get_overlap(text: str, overlap_tokens: int) -> str:
    """Extract last N tokens from text as overlap."""
    words = text.split()
    if len(words) <= overlap_tokens:
        return text
    return " ".join(words[-overlap_tokens:])
