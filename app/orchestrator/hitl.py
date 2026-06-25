"""Human-in-the-loop helpers for the AI Career Copilot.

Exposes:
- ``request_approval`` — builds the interrupt payload and suspends the graph.
- ``application_send_node`` — LangGraph node that gates application submission
  behind a human approval step.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from langgraph.types import interrupt

from app.orchestrator.state import CopilotState, HitlRequest


def request_approval(kind: str, payload: dict, prompt: str) -> Any:
    """Wrap LangGraph ``interrupt`` with a structured payload."""
    return interrupt({"kind": kind, "payload": payload, "prompt": prompt})


def application_send_node(state: CopilotState) -> dict:
    """LangGraph node: gate application submission with a human approval step.

    Returns a partial state dict containing ``application`` and
    ``hitl_request`` (as a plain dict — Pydantic models aren't
    msgpack-serializable by the Postgres checkpointer).
    """
    from app.api.applications import save_application  # noqa: PLC0415 (avoid circular at module level)

    application: dict = dict(state.get("application") or {})
    thread_id = state.get("thread_id", "")
    user_id = state.get("user_id", "")

    hitl_data = {
        "hitl_id": str(uuid4()),
        "thread_id": thread_id,
        "kind": "application_send",
        "question": "Review and approve this job application before sending",
        "context": {"application_package": application},
    }

    resume = interrupt({"hitl_request": hitl_data})

    approved: bool = bool((resume or {}).get("approved", False))
    application["status"] = "APPROVED" if approved else "REJECTED"

    # Persist the application so GET /applications returns it immediately.
    if user_id:
        save_application(user_id, application)

    # Store hitl_request as a plain dict — Pydantic BaseModel fails msgpack.
    hitl_req_dict: dict = {
        "kind": "application_send",
        "payload": application,
        "prompt": "Review and approve this job application before sending",
    }

    return {
        "application": application,
        "hitl_request": hitl_req_dict,
    }
