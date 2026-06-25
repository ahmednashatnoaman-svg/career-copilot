"""Runs API router — start runs, stream SSE, and resume HITL."""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/runs", tags=["runs"])

# ---------------------------------------------------------------------------
# In-memory fallback — used when Supabase is not configured (e.g. local dev
# without .env, or integration tests).  Production always uses Supabase.
# ---------------------------------------------------------------------------

_run_configs: dict[str, dict] = {}


def _save_run_config(thread_id: str, config: dict) -> None:
    """Persist run config: Supabase first, fall back to in-memory."""
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            db.table("runs").upsert(
                {
                    "thread_id": thread_id,
                    "user_id": config.get("user_id", "anonymous"),
                    "status": "running",
                    "message": config.get("message", ""),
                    "doc_ids": config.get("doc_ids", []),
                }
            ).execute()
            # Store full config payload in memory for the same request lifetime
            # so the subsequent SSE call on the same worker is fast.
            _run_configs[thread_id] = config
            return
        except Exception:  # noqa: BLE001
            pass  # fall through to in-memory
    _run_configs[thread_id] = config


def _load_run_config(thread_id: str) -> dict:
    """Load run config: check in-memory first, then Supabase."""
    if thread_id in _run_configs:
        return _run_configs[thread_id]

    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            result = (
                db.table("runs").select("*").eq("thread_id", thread_id).single().execute()
            )
            if result.data:
                config = {
                    "user_id": result.data.get("user_id", ""),
                    "message": result.data.get("message", ""),
                    "doc_ids": result.data.get("doc_ids") or [],
                    "resume_text": result.data.get("resume_text", ""),
                    "github_username": result.data.get("github_username", ""),
                    "github_token": result.data.get("github_token", ""),
                    "job_description": result.data.get("job_description", ""),
                }
                _run_configs[thread_id] = config
                return config
        except Exception:  # noqa: BLE001
            pass
    return {}


class RunRequest(BaseModel):
    user_id: str
    message: str
    doc_ids: list[str] = []
    resume_text: str = ""
    github_username: str = ""
    github_token: str = ""
    job_description: str = ""

# ---------------------------------------------------------------------------
# Supervisor injection hook — lets tests swap in a stub graph
# ---------------------------------------------------------------------------

_supervisor: Any = None  # compiled LangGraph graph


def get_supervisor() -> Any:
    return _supervisor


def set_supervisor(graph: Any) -> None:
    """Inject a supervisor graph (real or stub). Called at startup or in tests."""
    global _supervisor  # noqa: PLW0603
    _supervisor = graph


def _require_supervisor() -> Any:
    if _supervisor is None:
        raise RuntimeError(
            "Supervisor graph not initialised. "
            "Call app.api.runs.set_supervisor(graph) at startup."
        )
    return _supervisor


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

_SSE_DONE = "event: done\ndata: {}\n\n"


def _sse_frame(event: str, data: dict) -> str:
    """Format a single SSE frame per spec: event + data lines + blank line."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream_graph(
    graph: Any,
    initial_state: dict,
    config: dict,
) -> Generator[str, None, None]:
    """Iterate graph.stream() synchronously and yield SSE frames."""
    try:
        for chunk in graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, state_delta in chunk.items():
                if node_name == "__interrupt__":
                    raw = state_delta if hasattr(state_delta, "__iter__") else [state_delta]
                    interrupt_data = [getattr(i, "value", str(i)) for i in raw]
                    yield _sse_frame("interrupt", {"hitl_request": interrupt_data})
                    return
                elif isinstance(state_delta, dict) and "__interrupt__" in state_delta:
                    yield _sse_frame("interrupt", {"hitl_request": state_delta["__interrupt__"]})
                    return
                else:
                    yield _sse_frame("node", {"node": node_name, "data": state_delta})
    except Exception as exc:  # noqa: BLE001
        yield _sse_frame("error", {"detail": str(exc)})
    finally:
        yield _SSE_DONE


def _stream_graph_with_interrupt(
    graph: Any,
    initial_state: dict,
    config: dict,
) -> Generator[str, None, None]:
    """Wrap _stream_graph and catch LangGraph GraphInterrupt exceptions."""
    try:
        from langgraph.errors import GraphInterrupt
        _GraphInterrupt = GraphInterrupt
    except ImportError:
        _GraphInterrupt = None  # type: ignore[assignment,misc]

    try:
        yield from _stream_graph(graph, initial_state, config)
    except Exception as exc:  # noqa: BLE001
        if _GraphInterrupt is not None and isinstance(exc, _GraphInterrupt):
            interrupts = exc.args[0] if exc.args else ()
            hitl_data = [getattr(i, "value", str(i)) for i in (interrupts or [])]
            yield _sse_frame("interrupt", {"hitl_request": hitl_data})
        else:
            yield _sse_frame("error", {"detail": str(exc)})
        yield _SSE_DONE


# ---------------------------------------------------------------------------
# POST /runs
# ---------------------------------------------------------------------------


@router.post("")
async def create_run(body: RunRequest):
    """Start a new supervisor run. Persists config to Supabase so any worker
    can hydrate the SSE stream from the same source of truth."""
    thread_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    config = {
        "user_id": body.user_id,
        "message": body.message,
        "doc_ids": body.doc_ids,
        "resume_text": body.resume_text,
        "github_username": body.github_username,
        "github_token": body.github_token,
        "job_description": body.job_description,
    }
    _save_run_config(thread_id, config)

    return {"run_id": run_id, "thread_id": thread_id}


# ---------------------------------------------------------------------------
# GET /runs/{thread_id}/stream
# ---------------------------------------------------------------------------


@router.get("/{thread_id}/stream")
async def stream_run(
    thread_id: str,
    user_id: str,
    message: str = "",
):
    """Stream supervisor execution as SSE.

    Loads run config from Supabase (falls back to in-memory) so the stream
    works correctly in multi-worker or post-restart scenarios.
    """
    graph = _require_supervisor()

    config_data = _load_run_config(thread_id)

    initial_state: dict = {
        "user_id": user_id,
        "thread_id": thread_id,
        "user_message": message or config_data.get("message", ""),
        "uploaded_doc_ids": config_data.get("doc_ids", []),
        "resume_text": config_data.get("resume_text", ""),
        "github_username": config_data.get("github_username", ""),
        "github_token": config_data.get("github_token", ""),
        "job_description": config_data.get("job_description", ""),
    }
    config = {"configurable": {"thread_id": thread_id}}

    async def _generate():
        frames: list[str] = await run_in_threadpool(
            lambda: list(_stream_graph_with_interrupt(graph, initial_state, config))
        )
        for frame in frames:
            yield frame

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /runs/{thread_id}/resume
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/resume")
async def resume_run(
    thread_id: str,
    decision: dict = Body(...),  # noqa: B008
):
    """Resume a suspended run with a HITL decision.

    Body must be exactly the shape the HITL node expects: ``{"approved": true}``.
    """
    from langgraph.types import Command  # noqa: PLC0415

    graph = _require_supervisor()
    config = {"configurable": {"thread_id": thread_id}}

    cmd = Command(resume=decision)

    frames: list[str] = await run_in_threadpool(
        lambda: list(_stream_graph_with_interrupt(graph, cmd, config))
    )

    return {"status": "resumed", "frames": frames}
