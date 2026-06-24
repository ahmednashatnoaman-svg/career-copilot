"""Supervisor StateGraph — wires router, agents, critic, HITL, and aggregate.

Topology
--------
START → router
router → (dispatch_agent conditional)
dispatch_agent → one of: cv_analysis | rag | market | coaching
   … each agent node advances the plan and jumps back to dispatch_agent
   … when plan is exhausted, dispatch_agent → critic
critic → (critic_route conditional)
   accept    → aggregate → END
   regenerate → dispatch_agent   (restart plan walk)
   escalate  → application_send → END

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

from langgraph.graph import END, START, StateGraph

from app.agents.coaching.graph import build_coaching_graph
from app.agents.coaching.schemas import ChatRequest
from app.agents.cv_analysis.integration.graph_node import cv_analysis_node
from app.agents.market_research.adapter import market_node
from app.agents.market_research.schemas import MarketAgentInput, WorkPreferences
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
    agent_input = {
        "resume_text": state.get("resume_text"),           # type: ignore[attr-defined]
        "resume_file_bytes": state.get("resume_file_bytes"),  # type: ignore[attr-defined]
        "resume_filename": state.get("resume_filename"),   # type: ignore[attr-defined]
        # Pass user_message as job_description to enable tailored mode when present
        "job_description": state.get("user_message") or None,
    }
    result = cv_analysis_node(agent_input)  # type: ignore[arg-type]
    return _advance_plan(state, result)


def _rag_wrapper(state: CopilotState) -> dict:
    """RAG node already speaks CopilotState — just advance the plan."""
    result = rag_node(state)
    return _advance_plan(state, result)


def _market_wrapper(state: CopilotState) -> dict:
    """Build a minimal MarketAgentInput from CopilotState and invoke market_node."""
    user_message: str = state.get("user_message") or ""
    user_id: str = state.get("user_id") or "unknown"

    market_input = MarketAgentInput(
        user_id=user_id,
        query=user_message,
        target_roles=[],
        skills=[],
        experience_years=0,
        preferred_locations=[],
        work_preferences=WorkPreferences(),
    )
    result = market_node({"market_input": market_input})
    return _advance_plan(state, result)


def _coaching_wrapper(state: CopilotState) -> dict:
    """Build a ChatRequest from CopilotState, invoke coaching graph, map output."""
    user_id: str = state.get("user_id") or "demo_user"
    thread_id: str = state.get("thread_id") or "demo_thread"
    message: str = state.get("user_message") or ""

    request = ChatRequest(
        user_id=user_id,
        thread_id=thread_id,
        message=message or "hello",
    )

    # Build a fresh (no-checkpointer) coaching graph for this invocation so
    # that it does not try to connect to Postgres at graph-compile time.
    # The supervisor's own checkpointer handles persistence at the outer level.
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
}

_DISPATCH_TARGET_LABELS = {
    "cv_analysis": "cv_analysis",
    "rag": "rag",
    "market": "market",
    "coaching": "coaching",
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


def _aggregate_node(state: CopilotState) -> dict:
    """Compose a human-readable ``final_answer`` from whatever namespaced outputs are present."""
    parts: list[str] = []

    if cv := state.get("cv_analysis"):
        parts.append(f"[CV Analysis]\n{cv}")

    if rag_out := state.get("rag"):
        answer = rag_out.get("answer", "") if isinstance(rag_out, dict) else str(rag_out)
        parts.append(f"[Knowledge Base]\n{answer}")

    if market_out := state.get("market"):
        parts.append(f"[Market Research]\n{market_out}")

    if coaching_out := state.get("coaching"):
        response = (
            coaching_out.get("response", "")
            if isinstance(coaching_out, dict)
            else str(coaching_out)
        )
        parts.append(f"[Coaching]\n{response}")

    final_answer = "\n\n".join(parts) if parts else "No agent output was produced."
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
    builder.add_node("critic", critic_node)
    builder.add_node("application_send", application_send_node)
    builder.add_node("aggregate", _aggregate_node)

    # --- Entry edge ---
    builder.add_edge(START, "router")

    # --- Router → dispatch (router sets plan + next_agent) ---
    builder.add_conditional_edges(
        "router",
        _dispatch_route,
        {
            "cv_analysis": "cv_analysis",
            "rag": "rag",
            "market": "market",
            "coaching": "coaching",
            "critic": "critic",
        },
    )

    # --- Each agent loops back to re-dispatch (sequential plan walk) ---
    for agent_name in _AGENT_MAP:
        builder.add_conditional_edges(
            agent_name,
            _dispatch_route,
            {
                "cv_analysis": "cv_analysis",
                "rag": "rag",
                "market": "market",
                "coaching": "coaching",
                "critic": "critic",
            },
        )

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
