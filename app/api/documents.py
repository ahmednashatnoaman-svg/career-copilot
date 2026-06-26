"""Documents API router — upload and ingest documents."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.rag.ingest import ingest_document as _default_ingest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# ---------------------------------------------------------------------------
# Dependency injection hook — lets tests swap out the ingest callable
# ---------------------------------------------------------------------------

_ingest_fn: Callable = _default_ingest


def get_ingest_fn() -> Callable:
    return _ingest_fn


def override_ingest_fn(fn: Callable) -> None:
    """Replace the ingest function (called by tests to inject a stub)."""
    global _ingest_fn  # noqa: PLW0603
    _ingest_fn = fn


def reset_ingest_fn() -> None:
    """Restore the default ingest function."""
    global _ingest_fn  # noqa: PLW0603
    _ingest_fn = _default_ingest


# ---------------------------------------------------------------------------
# POST /documents
# ---------------------------------------------------------------------------


@router.post("")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    ingest_fn: Callable = Depends(get_ingest_fn),  # noqa: B008
):
    """Upload a document and ingest it into the RAG store.

    Returns:
        JSON with ``doc_id`` (str) and ``chunks`` (int).
    """
    user_id: str = getattr(request.state, "user_id", "")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    doc_id = str(uuid.uuid4())
    filename = file.filename or "upload.txt"

    try:
        chunks = await run_in_threadpool(
            ingest_fn,
            user_id,
            doc_id,
            file_bytes=file_bytes,
            filename=filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Best-effort: persist document metadata to Supabase.
    # Silently ignored when Supabase is unconfigured or user_id is not a
    # real Supabase UUID (e.g. "demo-user" used in onboarding).
    try:
        from app.services.supabase_db import get_client  # noqa: PLC0415

        db = get_client()
        if db is not None:
            db.table("documents").insert(
                {
                    "id": doc_id,
                    "user_id": user_id,
                    "filename": filename,
                    "chunks": chunks,
                }
            ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase document insert failed: %s", exc)

    return {"doc_id": doc_id, "chunks": chunks}
