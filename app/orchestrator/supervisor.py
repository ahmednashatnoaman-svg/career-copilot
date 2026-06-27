"""Supervisor StateGraph — wires router, agents, critic, HITL, and aggregate.

Topology
--------
START → router
router → (dispatch_agent conditional)
dispatch_agent → one of: cv_analysis | rag | market | coaching |
                          matching | portfolio | career_planning | application
   … each agent node advances the plan and jumps back to dispatch_agent
   … when plan is exhausted, dispatch_agent → critic
critic → (critic_route conditional)
   accept    → aggregate → END
   regenerate → dispatch_agent   (restart plan walk)
   escalate  → application_send → END

application (generation) → application_send → END

Sequential plan-walk rationale
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A clean parallel fan-out in a single StateGraph pass requires either
``Send`` / ``map-reduce`` or careful bookkeeping of which parallel branches
have finished before critic can fire.  The sequential walk (one agent at a
time, looping via ``dispatch_agent``) compiles cleanly, is simpler to reason
about, and is ACCEPTABLE per the task brief when a clean parallel fan-out is
hard to achieve reliably.
"""

from __future__ import annotations

import asyncio

from langgraph.graph import END, START, StateGraph

from app.agents.application.agent import application_node
from app.agents.career_planning.agent import career_planning_node
from app.agents.coaching.graph import build_coaching_graph
from app.agents.coaching.schemas import ChatRequest
from app.agents.cv_analysis.integration.graph_node import cv_analysis_node
from app.agents.market_research.adapter import market_node
from app.agents.market_research.schemas import MarketAgentInput, WorkPreferences
from app.agents.matching.agent import matching_node
from app.agents.portfolio.agent import portfolio_node
from app.agents.rag.agent import rag_node
from app.orchestrator.critic import critic_node, critic_route
from app.orchestrator.hitl import application_send_node
from app.orchestrator.router import route
from app.orchestrator.state import CopilotState

# ---------------------------------------------------------------------------
# Thin wrapper nodes — translate CopilotState → each agent's own input
# ---------------------------------------------------------------------------


def _cv_analysis_wrapper(state: CopilotState) -> dict:
    """Map CopilotState → CVAnalysisInputState and return namespaced output."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    agent_input = {
        "resume_text": state.get("resume_text"),           # type: ignore[attr-defined]
        "resume_file_bytes": state.get("resume_file_bytes"),  # type: ignore[attr-defined]
        "resume_filename": state.get("resume_filename"),   # type: ignore[attr-defined]
        # Pass user_message as job_description to enable tailored mode when present
        "job_description": state.get("user_message") or None,
    }
    try:
        result = cv_analysis_node(agent_input)  # type: ignore[arg-type]
        return _advance_plan(state, result)
    except Exception as exc:
        _log.warning("cv_analysis agent failed (%s) — advancing plan", exc)
        return _advance_plan(state, {"cv_analysis": {}})


def _rag_wrapper(state: CopilotState) -> dict:
    """RAG node already speaks CopilotState — just advance the plan."""
    result = rag_node(state)
    return _advance_plan(state, result)


def _market_wrapper(state: CopilotState) -> dict:
    """Build MarketAgentInput from CopilotState, enriched with CV analysis output."""
    user_message: str = state.get("user_message") or ""
    user_id: str = state.get("user_id") or "unknown"

    # Pull target_roles and skills from cv_analysis when it ran before market.
    # LangGraph may keep the value as a Pydantic model or serialise it to dict.
    target_roles: list[str] = []
    skills: list[str] = []
    cv = state.get("cv_analysis")
    if cv is not None:
        if hasattr(cv, "entities"):                               # Pydantic model
            target_roles = list(cv.entities.job_titles or [])
            skills = list(cv.entities.skills or [])
        elif isinstance(cv, dict):                                # serialised dict
            entities = cv.get("entities") or {}
            if isinstance(entities, dict):
                target_roles = list(entities.get("job_titles") or [])
                skills = list(entities.get("skills") or [])

    market_input = MarketAgentInput(
        user_id=user_id,
        query=user_message,
        target_roles=target_roles,
        skills=skills,
        experience_years=0,
        preferred_locations=[],
        work_preferences=WorkPreferences(),
    )
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        result = market_node({"market_input": market_input})
        return _advance_plan(state, result)
    except Exception as exc:
        _log.warning("market agent failed (%s) — advancing plan", exc)
        return _advance_plan(state, {"market": "Market analysis is currently unavailable."})


def _coaching_wrapper(state: CopilotState) -> dict:
    """Build a ChatRequest from CopilotState, invoke coaching graph, map output."""
    import logging as _logging  # noqa: PLC0415
    _log = _logging.getLogger(__name__)

    user_id: str = state.get("user_id") or "demo_user"
    thread_id: str = state.get("thread_id") or "demo_thread"
    message: str = state.get("user_message") or ""

    _empty_output: dict = {"coaching": {"response": "", "sub_intent": "", "next_action": "", "validation": {}}}

    try:
        request = ChatRequest(
            user_id=user_id,
            thread_id=thread_id,
            message=message or "hello",
        )

        # Build a fresh (no-checkpointer) coaching graph for this invocation so
        # that it does not try to connect to Postgres at graph-compile time.
        coaching_compiled = build_coaching_graph(checkpointer=None)
        config = {"configurable": {"thread_id": f"{user_id}:{thread_id}"}}
        coach_input = {
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "message": request.message,
            "mode": request.mode,
            "profile": request.profile.model_dump(exclude_none=True),
            "max_interview_questions": request.max_interview_questions,
        }
        result_state = coaching_compiled.invoke(coach_input, config=config)

        coaching_output = {
            "coaching": {
                "response": result_state.get("response", ""),
                "sub_intent": result_state.get("sub_intent", ""),
                "next_action": result_state.get("next_action", ""),
                "validation": result_state.get("validation", {}),
            }
        }
        return _advance_plan(state, coaching_output)

    except Exception as exc:  # noqa: BLE001
        # Coaching is best-effort: a DB error (e.g. pgvector not installed)
        # must not block the application HITL flow.
        _log.warning("coaching agent failed (%s) — advancing plan with empty response", exc)
        return _advance_plan(state, _empty_output)


def _matching_wrapper(state: CopilotState) -> dict:
    """Invoke matching_node and advance the plan."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        result = matching_node(state)
        return _advance_plan(state, result)
    except Exception as exc:
        _log.warning("matching agent failed (%s) — advancing plan", exc)
        return _advance_plan(state, {"matching": []})


def _portfolio_wrapper(state: CopilotState) -> dict:
    """Invoke portfolio_node (async) synchronously and advance the plan.

    asyncio.run() is safe here: the supervisor graph always executes inside
    run_in_threadpool() (see app/api/runs.py), which dispatches to a thread
    that has no running event loop, so asyncio.run() creates a fresh one.
    It would raise RuntimeError only when called from within an already-running
    event loop — that is not the case in this execution path.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        result = asyncio.run(portfolio_node(state))
        return _advance_plan(state, result)
    except Exception as exc:
        _log.warning("portfolio agent failed (%s) — advancing plan", exc)
        return _advance_plan(state, {"portfolio": {}})


def _career_planning_wrapper(state: CopilotState) -> dict:
    """Invoke career_planning_node and advance the plan."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        result = career_planning_node(state)
        return _advance_plan(state, result)
    except Exception as exc:
        _log.warning("career_planning agent failed (%s) — advancing plan", exc)
        return _advance_plan(state, {"career_planning": "Career planning is currently unavailable."})


def _application_wrapper(state: CopilotState) -> dict:
    """Invoke application_node (generation) and advance the plan.

    This node generates the draft application package.  It does NOT submit;
    that is handled by application_send (HITL gate) which follows immediately.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        result = application_node(state)
        return _advance_plan(state, result)
    except Exception as exc:
        _log.warning("application agent failed (%s) — advancing plan", exc)
        return _advance_plan(state, {"application_package": None})


# ---------------------------------------------------------------------------
# Plan-walk helpers
# ---------------------------------------------------------------------------


def _advance_plan(state: CopilotState, agent_output: dict) -> dict:
    """Return agent_output merged with an updated ``next_agent``.

    Pops the first item off the current plan (the agent that just ran) and
    sets ``next_agent`` to the next item, or ``None`` when plan is exhausted.
    """
    plan: list[str] = list(state.get("plan") or [])
    if plan:
        plan = plan[1:]          # remove the agent that just completed
    next_agent = plan[0] if plan else None
    return {**agent_output, "plan": plan, "next_agent": next_agent}


# ---------------------------------------------------------------------------
# Dispatch node + conditional edge
# ---------------------------------------------------------------------------

#: Maps plan agent name → wrapper callable
_AGENT_MAP = {
    "cv_analysis": _cv_analysis_wrapper,
    "rag": _rag_wrapper,
    "market": _market_wrapper,
    "coaching": _coaching_wrapper,
    "matching": _matching_wrapper,
    "portfolio": _portfolio_wrapper,
    "career_planning": _career_planning_wrapper,
    "application": _application_wrapper,
}

_DISPATCH_TARGET_LABELS = {
    "cv_analysis": "cv_analysis",
    "rag": "rag",
    "market": "market",
    "coaching": "coaching",
    "matching": "matching",
    "portfolio": "portfolio",
    "career_planning": "career_planning",
    "application": "application",
    None: "critic",          # plan exhausted → proceed to critic
}


def _dispatch_route(state: CopilotState) -> str:
    """Return the edge label for the dispatch conditional.

    If ``next_agent`` names a known agent, route to that agent node.
    When ``next_agent`` is absent or unknown, fall through to critic.
    """
    next_agent = state.get("next_agent")
    if next_agent in _AGENT_MAP:
        return next_agent
    return "critic"


# ---------------------------------------------------------------------------
# Aggregate node
# ---------------------------------------------------------------------------


def _to_dict(obj: any) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return getattr(obj, "__dict__", {})

def _aggregate_node(state: CopilotState) -> dict:
    """Compose a human-readable ``final_answer`` from whatever namespaced outputs are present."""
    parts: list[str] = []

    if cv := state.get("cv_analysis"):
        cv = _to_dict(cv)
        summary = cv.get("summary", "")
        skills = ", ".join(cv.get("skills", []))
        parts.append(f"### 📄 CV Analysis\n\n**Summary:** {summary}\n\n**Skills:** {skills}")

    if rag_out := state.get("rag"):
        answer = rag_out.get("answer", "") if isinstance(rag_out, dict) else str(rag_out)
        parts.append(f"### 📚 Knowledge Base\n\n{answer}")

    if matching_out := state.get("matching"):
        matching_out = _to_dict(matching_out)
        ranked = matching_out.get("ranked", [])
        if ranked:
            lines = ["### 🎯 Top Job Matches\n"]
            for i, match in enumerate(ranked, 1):
                match = _to_dict(match)
                job = _to_dict(match.get("job", {}))
                title = job.get("title", "Unknown Role")
                company = job.get("company", "Unknown Company")
                url = job.get("url", "#")
                score = match.get("score", 0.0)
                rationale = match.get("rationale", "")
                
                lines.append(f"{i}. **[{title}]({url})** at {company} *(Match Score: {score:.2f})*")
                if rationale:
                    lines.append(f"   - *Why it's a match:* {rationale}")
            parts.append("\n".join(lines))
            
    if market_out := state.get("market"):
        market_out = _to_dict(market_out)
        jobs = market_out.get("jobs", [])
        if jobs:
            lines = ["### 💼 Market Research (Jobs Found)\n"]
            for i, job in enumerate(jobs, 1):
                job = _to_dict(job)
                title = job.get("title", "Unknown Role")
                company = job.get("company", "Unknown Company")
                url = job.get("url", "#")
                lines.append(f"{i}. **[{title}]({url})** at {company}")
            parts.append("\n".join(lines))

    if portfolio_out := state.get("portfolio"):
        portfolio_out = _to_dict(portfolio_out)
        analysis = portfolio_out.get("analysis", "")
        parts.append(f"### 💻 Portfolio Analysis\n\n{analysis}")

    if career_plan_out := state.get("career_plan"):
        career_plan_out = _to_dict(career_plan_out)
        plan = career_plan_out.get("plan", "")
        parts.append(f"### 🗺️ Career Plan\n\n{plan}")

    if coaching_out := state.get("coaching"):
        coaching_out = _to_dict(coaching_out)
        response = (
            coaching_out.get("response", "")
            if isinstance(coaching_out, dict)
            else str(coaching_out)
        )
        parts.append(f"### 🤝 Coaching\n\n{response}")

    final_answer = "\n\n---\n\n".join(parts) if parts else "No agent output was produced."
    return {"final_answer": final_answer}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_supervisor(checkpointer=None):
    """Build and compile the supervisor StateGraph.

    Args:
        checkpointer: An optional LangGraph checkpointer (e.g. PostgresSaver).
            Pass ``None`` to compile without persistence — useful for unit tests
            that do not have a live database.

    Returns:
        A compiled LangGraph ``CompiledGraph``.
    """
    builder = StateGraph(CopilotState)

    # --- Core nodes ---
    builder.add_node("router", route)
    builder.add_node("cv_analysis", _cv_analysis_wrapper)
    builder.add_node("rag", _rag_wrapper)
    builder.add_node("market", _market_wrapper)
    builder.add_node("coaching", _coaching_wrapper)
    builder.add_node("matching", _matching_wrapper)
    builder.add_node("portfolio", _portfolio_wrapper)
    builder.add_node("career_planning", _career_planning_wrapper)
    builder.add_node("application", _application_wrapper)
    builder.add_node("critic", critic_node)
    builder.add_node("application_send", application_send_node)
    builder.add_node("aggregate", _aggregate_node)

    # --- Entry edge ---
    builder.add_edge(START, "router")

    # Full dispatch map: all agent nodes + critic fallback
    _dispatch_map = {agent: agent for agent in _AGENT_MAP} | {"critic": "critic"}

    # --- Router → dispatch (router sets plan + next_agent) ---
    builder.add_conditional_edges(
        "router",
        _dispatch_route,
        _dispatch_map,
    )

    # --- Each plan-walk agent loops back to re-dispatch (sequential plan walk) ---
    # application routes to application_send (HITL gate) after generating the package,
    # rather than looping back to dispatch like the other plan agents.
    _plan_agents = {k for k in _AGENT_MAP if k != "application"}
    _plan_agent_dispatch_map = {agent: agent for agent in _plan_agents} | {
        "critic": "critic",
        "application_send": "application_send",
        "application": "application",
    }

    for agent_name in _plan_agents:
        builder.add_conditional_edges(
            agent_name,
            _dispatch_route,
            _plan_agent_dispatch_map,
        )

    # application (generation) always proceeds directly to application_send
    builder.add_edge("application", "application_send")

    # --- Critic conditional ---
    builder.add_conditional_edges(
        "critic",
        critic_route,
        {
            "accept": "aggregate",
            "regenerate": "router",   # re-plan and re-dispatch
            "escalate": "application_send",
        },
    )

    # --- Terminal edges ---
    builder.add_edge("aggregate", END)
    builder.add_edge("application_send", END)

    return builder.compile(checkpointer=checkpointer)
