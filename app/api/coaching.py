"""Coaching API router — standalone chat endpoint for career coaching."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Request

router = APIRouter(prefix="/coaching", tags=["coaching"])

_coaching_graph: Any = None


def _get_coaching_graph() -> Any:
    global _coaching_graph  # noqa: PLW0603
    if _coaching_graph is None:
        from app.agents.coaching.graph import build_coaching_graph  # noqa: PLC0415

        _coaching_graph = build_coaching_graph(checkpointer=None)
    return _coaching_graph


@router.post("/chat")
async def coaching_chat(
    request: Request,
    message: str = Body(...),
    thread_id: str = Body(None),
    mode: str = Body("general"),
    profile: dict = Body({}),  # noqa: B008
):
    """Chat with the career coaching agent.

    Body:
        user_id:   The user's ID.
        message:   The user's message.
        thread_id: Optional existing thread ID (new one created if omitted).
        mode:      Coaching mode — e.g. "general", "interview", "cv".
        profile:   Optional user profile dict for personalised coaching.

    Returns:
        JSON with ``thread_id``, ``response``, and ``mode``.
    """
    user_id: str = getattr(request.state, "user_id", "")
    if not thread_id:
        thread_id = str(uuid.uuid4())

    try:
        graph = _get_coaching_graph()
        config = {"configurable": {"thread_id": f"{user_id}:{thread_id}"}}
        result = graph.invoke(
            {
                "user_id": user_id,
                "thread_id": thread_id,
                "message": message,
                "mode": mode,
                "profile": profile or {},
            },
            config=config,
        )
        response = result.get("response", "I'm here to help with your career!")
        return {
            "thread_id": thread_id,
            "response": response,
            "mode": result.get("sub_intent", mode),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "thread_id": thread_id,
            "response": f"Coach unavailable: {exc}",
            "mode": mode,
        }
