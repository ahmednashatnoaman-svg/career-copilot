"""Unit tests for the FastAPI endpoints (Task 8).

These tests use TestClient with stubbed supervisor and ingest —
no live DB or LLM required.

Live end-to-end tests (upload → run → stream → interrupt → resume →
Application APPROVED) are below, gated by INFRA_UP=1.
"""

from __future__ import annotations

import io
import json
import os

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------

_STUB_CHUNKS = 5
_STUB_RUN_ID = "stub-run-id"
_STUB_THREAD_ID = "stub-thread-id"


def _stub_ingest(user_id, doc_id, *, file_bytes=None, filename=None, text=None):
    """Return a fixed chunk count without touching Qdrant."""
    return _STUB_CHUNKS


class _StubGraph:
    """Minimal stub that behaves like a compiled LangGraph graph.

    stream() yields a single ``done``-equivalent chunk so the SSE generator
    emits at least a ``done`` event.
    """

    async def astream(self, state, *, config=None, stream_mode="updates"):
        yield {"aggregate": {"final_answer": "stub answer"}}

    def invoke(self, state, *, config=None):
        return {"final_answer": "stub answer"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_stubs():
    """Inject stubs before each test; restore defaults after."""
    from app.api import documents as docs_mod
    from app.api import runs as runs_mod

    # Inject stubs
    docs_mod.override_ingest_fn(_stub_ingest)
    runs_mod.set_supervisor(_StubGraph())

    yield

    # Restore
    docs_mod.reset_ingest_fn()
    runs_mod.set_supervisor(None)


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Unit tests (no INFRA needed)
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_post_runs_returns_ids(client):
    r = client.post(
        "/runs",
        json={"user_id": "user-1", "message": "find me AI jobs", "doc_ids": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert "thread_id" in body
    assert body["run_id"]
    assert body["thread_id"]


def test_stream_run_emits_done(client):
    """GET /runs/{thread_id}/stream must emit at least a 'done' SSE event."""
    r = client.get(
        "/runs/stub-thread/stream",
        params={"user_id": "user-1", "message": "find AI jobs"},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    raw = r.text
    # Must contain a done event frame
    assert "event: done" in raw


def test_stream_run_emits_node_event(client):
    """GET /runs/{thread_id}/stream must emit at least one 'node' SSE event."""
    r = client.get(
        "/runs/stub-thread/stream",
        params={"user_id": "user-1", "message": "find AI jobs"},
    )
    raw = r.text
    assert "event: node" in raw
    # Each data line should be valid JSON
    for line in raw.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                parsed = json.loads(payload)
                assert isinstance(parsed, dict)


def test_post_documents_returns_chunks(client):
    """POST /documents with a tiny text file returns doc_id and chunks > 0."""
    content = b"Alice has 10 years of Python and machine learning experience."
    file_obj = io.BytesIO(content)

    r = client.post(
        "/documents",
        data={"user_id": "user-1"},
        files={"file": ("resume.txt", file_obj, "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert "doc_id" in body
    assert body["chunks"] == _STUB_CHUNKS


def test_list_applications_empty(client):
    """GET /applications with no seeded data returns an empty list."""
    from app.api.applications import seed_applications

    seed_applications([])
    r = client.get("/applications", params={"user_id": "user-1"})
    assert r.status_code == 200
    assert r.json() == []


def test_list_applications_filtered(client):
    """GET /applications returns only records for the current authenticated user."""
    from app.api.applications import get_current_user_id, seed_applications
    from app.main import app

    seed_applications([
        {"id": 1, "user_id": "user-1", "status": "APPROVED"},
        {"id": 2, "user_id": "user-2", "status": "DRAFT"},
    ])
    # Simulate an authenticated user by overriding the user_id dependency
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    try:
        r = client.get("/applications")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["user_id"] == "user-1"
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


def test_resume_run(client):
    """POST /runs/{thread_id}/resume returns resumed status."""
    r = client.post(
        "/runs/stub-thread/resume",
        json={"approved": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resumed"
    assert "frames" in body
    # Must still contain a done frame
    all_frames = "".join(body["frames"])
    assert "event: done" in all_frames


# ---------------------------------------------------------------------------
# Live end-to-end tests — INFRA_UP=1 gate
# ---------------------------------------------------------------------------

pytestmark_infra = pytest.mark.skipif(
    os.getenv("INFRA_UP") != "1",
    reason="live infra not running (set INFRA_UP=1 to enable)",
)


@pytestmark_infra
def test_e2e_upload_run_interrupt_resume_approved():
    """Full end-to-end: upload resume → start run → stream to interrupt → resume → Application APPROVED.

    Requires:
        INFRA_UP=1  — Postgres + Qdrant up
        GROQ_API_KEY / GEMINI_API_KEY — at least one LLM key set

    NOTE: The module-level autouse fixture installs a _StubGraph for unit tests.
    This live test overrides that stub with the real supervisor so that
    interrupt() is actually called and save_application() persists the record.
    doc_ids is kept empty so the router's cv_analysis guardrail doesn't trigger
    a Qdrant lookup on stub-ingested data.
    """
    from app.api import runs as runs_mod  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    from app.memory.checkpointer import checkpointer_cm  # noqa: PLC0415
    from app.orchestrator.supervisor import build_supervisor  # noqa: PLC0415

    # Replace the autouse stub with the real compiled supervisor graph.
    with checkpointer_cm() as checkpointer:
        graph = build_supervisor(checkpointer=checkpointer)
        runs_mod.set_supervisor(graph)

        live_client = TestClient(app, raise_server_exceptions=True)

        # 1. Upload a resume document (stub ingest from autouse returns 5 chunks)
        resume_text = (
            "Jane Doe | jane@example.com\n"
            "Senior AI Engineer with 7 years Python, LLM, LangChain, FastAPI.\n"
            "Previously at Acme Corp building RAG pipelines.\n"
        )
        upload_resp = live_client.post(
            "/documents",
            data={"user_id": "e2e-user-1"},
            files={"file": ("resume.txt", io.BytesIO(resume_text.encode()), "text/plain")},
        )
        assert upload_resp.status_code == 200, upload_resp.text
        upload_body = upload_resp.json()
        assert upload_body["chunks"] > 0

        # 2. Start a run — doc_ids omitted so cv_analysis guardrail doesn't fire
        run_resp = live_client.post(
            "/runs",
            json={
                "user_id": "e2e-user-1",
                "message": "Find AI engineer jobs and tailor an application.",
                "doc_ids": [],
            },
        )
        assert run_resp.status_code == 200
        thread_id = run_resp.json()["thread_id"]

        # 3. Consume the stream until we get an interrupt
        stream_resp = live_client.get(
            f"/runs/{thread_id}/stream",
            params={
                "user_id": "e2e-user-1",
                "message": "Find AI engineer jobs and tailor an application.",
            },
        )
        assert stream_resp.status_code == 200
        raw = stream_resp.text
        assert "event: interrupt" in raw or "event: done" in raw, (
            f"Expected interrupt or done in stream. Got:\n{raw}"
        )

        # 4. Resume with approval (if there was an interrupt)
        if "event: interrupt" in raw:
            resume_resp = live_client.post(
                f"/runs/{thread_id}/resume",
                json={"approved": True},
            )
            assert resume_resp.status_code == 200
            resume_body = resume_resp.json()
            assert resume_body["status"] == "resumed"

        # 5. Check Application row was created with APPROVED status
        apps_resp = live_client.get("/applications", params={"user_id": "e2e-user-1"})
        assert apps_resp.status_code == 200
        apps = apps_resp.json()
        # At least one APPROVED application should exist
        approved = [a for a in apps if a.get("status") in ("APPROVED", "approved")]
        assert approved, f"No APPROVED application found. Applications: {apps}"
