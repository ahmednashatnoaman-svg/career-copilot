"""Interviews API router — mock interview session management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body

router = APIRouter(prefix="/interviews", tags=["interviews"])

# In-memory interview sessions (replace with Supabase later)
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


@router.post("/start")
async def start_interview(
    user_id: str = Body(...),
    role: str = Body(...),
    interview_type: str = Body("behavioral"),
    cv_summary: str = Body(""),
):
    """Start a new mock interview session.

    Body:
        user_id:        The user's ID.
        role:           Target job role (e.g. "Senior Software Engineer").
        interview_type: "behavioral" | "technical" | "system_design".
        cv_summary:     Optional CV summary for personalised questions.

    Returns:
        JSON with ``session_id``, ``question``, and ``question_number``.
    """
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
        pass  # use default question

    _sessions[session_id] = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "interview_type": interview_type,
        "messages": [{"role": "assistant", "content": first_question}],
        "score": 0,
        "question_count": 1,
        "status": "active",
    }

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
    """Submit an answer to the current interview question.

    Body:
        answer: The candidate's answer text.

    Returns:
        JSON with ``session_id``, ``feedback``, ``question_number``,
        ``status``, and ``is_complete``.
    """
    session = _sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}

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
        history.append(
            HumanMessage(content=f"[INTERVIEWER INSTRUCTION: {next_instruction}]")
        )
        response = await llm.ainvoke(history)
        feedback = response.content
    except Exception:  # noqa: BLE001
        pass  # use default feedback

    session["messages"].append({"role": "assistant", "content": feedback})
    session["question_count"] += 1

    if is_last:
        session["status"] = "completed"

    return {
        "session_id": session_id,
        "feedback": feedback,
        "question_number": session["question_count"],
        "status": session["status"],
        "is_complete": session["status"] == "completed",
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get interview session details.

    Returns:
        The full session dict, or ``{"error": "Session not found"}``.
    """
    session = _sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}
    return session
