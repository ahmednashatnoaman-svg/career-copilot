"""RAG document ingestion pipeline."""
from __future__ import annotations

from app.agents.cv_analysis.core.extraction.parser import extract_text
from app.rag.chunking import chunk_text
from app.rag.store import ensure_collection, upsert_chunks


def ingest_document(
    user_id: str,
    doc_id: str,
    *,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    text: str | None = None,
) -> int:
    """Ingest a document into the RAG store.

    Dispatches on input type:
    - Plain text: passthrough to chunking
    - Files (PDF/DOCX): parse via CV parser → chunk → upsert

    Args:
        user_id: User identifier for isolation.
        doc_id: Document identifier within the user's scope.
        file_bytes: Optional file bytes (requires filename).
        filename: Optional filename (required if file_bytes provided).
        text: Optional plain text (passthrough if provided).

    Returns:
        Number of chunks upserted into the store.

    Raises:
        ValueError: If neither text nor file_bytes+filename is provided,
                    or if both are provided.
        UnsupportedFileTypeError: If file type is not .pdf or .docx.
    """
    # Validate inputs: prefer text if provided, else require both file_bytes and filename
    if text and text.strip():
        # Text is provided and non-empty; use it
        pass
    elif file_bytes is not None and filename is not None:
        # Both file_bytes and filename are provided; use them
        pass
    else:
        # Neither valid text nor valid (file_bytes, filename) pair provided
        raise ValueError(
            "ingest_document requires either non-empty text, or both file_bytes and filename"
        )

    # Extract text from file or use provided text
    extracted_text = extract_text(
        file_bytes=file_bytes, filename=filename, raw_text=text
    )

    # Chunk the text
    chunks = chunk_text(extracted_text)

    # Ensure the Qdrant collection exists before writing (idempotent)
    ensure_collection()

    # Upsert into store and return chunk count
    return upsert_chunks(user_id=user_id, doc_id=doc_id, chunks=chunks)
