"""Coaching API router — standalone chat endpoint for career coaching."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body

router = APIRouter(prefix="/coaching", tags=["coaching"])


@router.post("/chat")
async def coaching_chat(
    user_id: str = Body(...),
    message: str = Body(...),
    thread_id: str = Body(None),
    mode: str = Body("general"),
    profile: dict = Body(default_factory=dict),
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
    if not thread_id:
        thread_id = str(uuid.uuid4())

    try:
        from app.agents.coaching.graph import build_coaching_graph  # noqa: PLC0415

        graph = build_coaching_graph(checkpointer=None)
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
        response = result.get("coaching", {}).get(
            "response", "I'm here to help with your career!"
        )
        return {
            "thread_id": thread_id,
            "response": response,
            "mode": result.get("coaching", {}).get("sub_intent", mode),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "thread_id": thread_id,
            "response": f"Coach unavailable: {exc}",
            "mode": mode,
        }
