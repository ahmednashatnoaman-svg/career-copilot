"""Human-in-the-loop helpers for the AI Career Copilot.

Exposes:
- ``request_approval`` — builds the interrupt payload and suspends the graph.
- ``application_send_node`` — LangGraph node that gates application submission
  behind a human approval step.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.orchestrator.state import CopilotState, HitlRequest


def request_approval(kind: str, payload: dict, prompt: str) -> Any:
    """Wrap LangGraph ``interrupt`` with a structured payload.

    Builds a dict matching the ``HitlRequest`` schema, suspends the graph via
    ``interrupt``, and returns whatever value the human resumes with.

    Args:
        kind:    The category of approval being requested.
        payload: Arbitrary context data to show the human reviewer.
        prompt:  Human-readable instruction / question.

    Returns:
        The resume value provided by the human (e.g. ``{"approved": True}``).
    """
    return interrupt({"kind": kind, "payload": payload, "prompt": prompt})


def application_send_node(state: CopilotState) -> dict:
    """LangGraph node: gate application submission with a human approval step.

    Reads ``state["application"]`` (gracefully handles missing / empty dict),
    builds a ``HitlRequest``, calls ``request_approval``, then sets
    ``application["status"]`` to ``"APPROVED"`` or ``"REJECTED"`` based on
    the human's resume payload.

    Returns a partial state dict containing ``application`` and
    ``hitl_request``.
    """
    application: dict = dict(state.get("application") or {})

    payload = {
        "job_title": application.get("job_title"),
        "company": application.get("company"),
        "cover_letter": application.get("cover_letter"),
    }
    prompt = (
        "Please review the application below and approve or reject it.\n"
        f"Company: {payload['company']}\n"
        f"Role: {payload['job_title']}"
    )

    hitl_req = HitlRequest(
        kind="application_send",
        payload=payload,
        prompt=prompt,
    )

    resume = request_approval(
        kind=hitl_req.kind,
        payload=hitl_req.payload,
        prompt=hitl_req.prompt,
    )

    approved: bool = bool((resume or {}).get("approved", False))
    application["status"] = "APPROVED" if approved else "REJECTED"

    return {
        "application": application,
        "hitl_request": hitl_req,
    }
