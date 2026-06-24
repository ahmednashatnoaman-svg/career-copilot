"""RAG document ingestion pipeline."""
from __future__ import annotations

from app.agents.cv_analysis.core.extraction.parser import extract_text
from app.rag.chunking import chunk_text
from app.rag.store import upsert_chunks


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
    # Extract text from file or use provided text
    extracted_text = extract_text(
        file_bytes=file_bytes, filename=filename, raw_text=text
    )

    # Chunk the text
    chunks = chunk_text(extracted_text)

    # Upsert into store and return chunk count
    return upsert_chunks(user_id=user_id, doc_id=doc_id, chunks=chunks)
