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
# In-memory run config store — keyed by thread_id
# ---------------------------------------------------------------------------

_run_configs: dict[str, dict] = {}


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
    """Iterate graph.stream() synchronously and yield SSE frames.

    Runs inside run_in_threadpool so it must NOT be async.
    The graph is always called synchronously to avoid the asyncio.run() bridge
    deadlock inside portfolio_node (which itself calls asyncio.run).
    """
    try:
        for chunk in graph.stream(initial_state, config=config, stream_mode="updates"):
            # chunk is {node_name: state_delta}
            for node_name, state_delta in chunk.items():
                # Detect interrupt / HITL — LangGraph yields {"__interrupt__": tuple[Interrupt]}
                # or embeds "__interrupt__" inside the state delta dict.
                if node_name == "__interrupt__":
                    # state_delta is a tuple of Interrupt namedtuples; extract .value from each
                    raw = state_delta if hasattr(state_delta, "__iter__") else [state_delta]
                    interrupt_data = [getattr(i, "value", str(i)) for i in raw]
                    yield _sse_frame("interrupt", {"hitl_request": interrupt_data})
                    return  # suspend here; resume via POST /resume
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
    # LangGraph raises GraphInterrupt when interrupt() is called inside a node.
    # We catch it here to emit a structured SSE interrupt frame.
    try:
        from langgraph.errors import GraphInterrupt
        _GraphInterrupt = GraphInterrupt
    except ImportError:
        _GraphInterrupt = None  # type: ignore[assignment,misc]

    try:
        yield from _stream_graph(graph, initial_state, config)
    except Exception as exc:  # noqa: BLE001
        if _GraphInterrupt is not None and isinstance(exc, _GraphInterrupt):
            # exc.args[0] is a tuple of Interrupt objects
            interrupts = exc.args[0] if exc.args else ()
            hitl_data = [
                getattr(i, "value", str(i)) for i in (interrupts or [])
            ]
            yield _sse_frame("interrupt", {"hitl_request": hitl_data})
        else:
            yield _sse_frame("error", {"detail": str(exc)})
        yield _SSE_DONE


# ---------------------------------------------------------------------------
# POST /runs
# ---------------------------------------------------------------------------


@router.post("")
async def create_run(body: RunRequest):
    """Start a new supervisor run for a user.

    Returns:
        JSON with ``run_id`` (str) and ``thread_id`` (str).
    """
    thread_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    # Store run config keyed by thread_id so stream_run can look it up.
    _run_configs[thread_id] = {
        "user_id": body.user_id,
        "message": body.message,
        "doc_ids": body.doc_ids,
        "resume_text": body.resume_text,
        "github_username": body.github_username,
        "github_token": body.github_token,
        "job_description": body.job_description,
    }

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

    Query params: ``user_id``, ``message`` (optional — config from POST /runs is preferred).

    Emits SSE frames::

        event: node
        data: {"node": "<name>", "data": {...}}

        event: interrupt
        data: {"hitl_request": {...}}

        event: done
        data: {}

    NOTE: The graph is invoked via run_in_threadpool to avoid deadlock with
    the asyncio.run() bridge inside portfolio_node.
    """
    graph = _require_supervisor()

    # Look up run config stored during POST /runs
    config_data = _run_configs.get(thread_id, {})

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
        # We collect frames in a threadpool to keep the sync graph
        # off the main event loop, then yield them to the ASGI client.
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

    Body: any dict, e.g. ``{"approved": true}``.

    Returns:
        JSON with ``status`` and collected ``frames`` (SSE events) as a list.
    """
    from langgraph.types import Command  # noqa: PLC0415

    graph = _require_supervisor()
    config = {"configurable": {"thread_id": thread_id}}

    cmd = Command(resume=decision)

    frames: list[str] = await run_in_threadpool(
        lambda: list(_stream_graph_with_interrupt(graph, cmd, config))
    )

    return {"status": "resumed", "frames": frames}
