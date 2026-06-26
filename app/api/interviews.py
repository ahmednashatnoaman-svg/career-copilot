"""Interviews API router — mock interview session management."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Body, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])

# In-memory fallback (used when Supabase is not configured or in tests)
_sessions: dict[str, dict] = {}

INTERVIEW_SYSTEM_PROMPT = (
    "You are an expert technical interviewer conducting a mock job interview. "
    "Ask relevant, challenging questions one at a time. After each answer:\n"
    "1. Provide brief feedback (1-2 sentences)\n"
    "2. Score the answer 1-5\n"
    "3. Ask the next question\n\n"
    "Be encouraging but honest. Focus on: {role} position.\n"
    "Keep responses concise and professional."
)


def _save_session(session: dict) -> None:
    """Persist session to Supabase or in-memory."""
    session_id = session["session_id"]
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            db.table("interview_sessions").upsert(
                {
                    "id": session_id,
                    "user_id": session["user_id"],
                    "role": session["role"],
                    "interview_type": session.get("interview_type", "behavioral"),
                    "messages": session.get("messages", []),
                    "question_count": session.get("question_count", 0),
                    "status": session.get("status", "active"),
                }
            ).execute()
            _sessions[session_id] = session
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("_save_session Supabase upsert failed: %s", exc)
    _sessions[session_id] = session


def _load_session(session_id: str) -> dict | None:
    """Load session from in-memory first, then Supabase."""
    if session_id in _sessions:
        return _sessions[session_id]

    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is not None:
        try:
            result = (
                db.table("interview_sessions")
                .select("*")
                .eq("id", session_id)
                .single()
                .execute()
            )
            if result.data:
                session = {
                    "session_id": result.data["id"],
                    "user_id": result.data["user_id"],
                    "role": result.data["role"],
                    "interview_type": result.data.get("interview_type", "behavioral"),
                    "messages": result.data.get("messages") or [],
                    "question_count": result.data.get("question_count", 0),
                    "status": result.data.get("status", "active"),
                }
                _sessions[session_id] = session
                return session
        except Exception:  # noqa: BLE001
            pass
    return None


@router.post("/start")
async def start_interview(
    user_id: str = Body(...),
    role: str = Body(...),
    interview_type: str = Body("behavioral"),
    cv_summary: str = Body(""),
):
    """Start a new mock interview session. Persists to Supabase."""
    session_id = str(uuid.uuid4())

    context = f"Candidate background: {cv_summary}" if cv_summary else ""
    first_q_prompt = (
        f"Start a {interview_type} interview for a {role} position. {context}\n"
        "Ask the FIRST interview question only. Be welcoming but professional."
    )

    first_question = f"Tell me about yourself and why you're interested in the {role} role."
    try:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        from app.llm.provider import get_llm  # noqa: PLC0415

        llm = get_llm("reason")
        response = await llm.ainvoke(
            [
                SystemMessage(content=INTERVIEW_SYSTEM_PROMPT.format(role=role)),
                HumanMessage(content=first_q_prompt),
            ]
        )
        first_question = response.content
    except Exception:  # noqa: BLE001
        pass

    session = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "interview_type": interview_type,
        "messages": [{"role": "assistant", "content": first_question}],
        "score": 0,
        "question_count": 1,
        "status": "active",
    }
    _save_session(session)

    return {
        "session_id": session_id,
        "question": first_question,
        "question_number": 1,
    }


@router.post("/{session_id}/answer")
async def answer_question(
    session_id: str,
    answer: str = Body(...),
):
    """Submit an answer. Loads and updates session from Supabase."""
    session = _load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session["messages"].append({"role": "user", "content": answer})

    max_questions = 5
    is_last = session["question_count"] >= max_questions

    next_instruction = (
        "End the interview with overall feedback and a total score /25."
        if is_last
        else "Give brief feedback on this answer, then ask the NEXT question."
    )

    feedback = "Good answer! " + (
        "That concludes our interview." if is_last else "Let's continue."
    )
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: PLC0415

        from app.llm.provider import get_llm  # noqa: PLC0415

        llm = get_llm("reason")
        history = [SystemMessage(content=INTERVIEW_SYSTEM_PROMPT.format(role=session["role"]))]
        for msg in session["messages"]:
            if msg["role"] == "user":
                history.append(HumanMessage(content=msg["content"]))
            else:
                history.append(AIMessage(content=msg["content"]))
        history.append(HumanMessage(content=f"[INTERVIEWER INSTRUCTION: {next_instruction}]"))
        response = await llm.ainvoke(history)
        feedback = response.content
    except Exception:  # noqa: BLE001
        pass

    session["messages"].append({"role": "assistant", "content": feedback})
    session["question_count"] += 1

    if is_last:
        session["status"] = "completed"

    _save_session(session)

    return {
        "session_id": session_id,
        "feedback": feedback,
        "question_number": session["question_count"],
        "status": session["status"],
        "is_complete": session["status"] == "completed",
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    session = _load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
