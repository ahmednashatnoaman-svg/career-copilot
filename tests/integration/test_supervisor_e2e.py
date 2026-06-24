"""End-to-end tests for the Supervisor graph.

Gate structure
--------------
- ``test_builds``        : no DB, no network — just compiles the graph and
                           asserts all expected node names are present.
- ``test_market_only_run``: live infra required (``INFRA_UP=1``).  Invokes a
                            thread that routes to ``market`` only and asserts
                            that a checkpoint was written and ``final_answer``
                            is set.
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Unit gate (always runs — no DB, no LLM)
# ---------------------------------------------------------------------------

EXPECTED_NODES = {
    "router",
    "cv_analysis",
    "rag",
    "market",
    "coaching",
    "critic",
    "application_send",
    "aggregate",
}


def test_builds():
    """build_supervisor(None) must compile and contain all expected node names."""
    from app.orchestrator.supervisor import build_supervisor

    graph = build_supervisor(checkpointer=None)
    node_names = set(graph.get_graph().nodes.keys())

    # LangGraph always adds __start__ and __end__ virtual nodes; filter them
    actual_nodes = {n for n in node_names if not n.startswith("__")}

    missing = EXPECTED_NODES - actual_nodes
    assert not missing, (
        f"Compiled graph is missing nodes: {missing}\n"
        f"Actual nodes: {actual_nodes}"
    )


def test_application_plan_entry_routes_to_hitl():
    """Test that 'application' in next_agent routes to application_send, not critic.
    
    When the router emits 'application' in the plan, _dispatch_route must
    return 'application_send' (the HITL gate), not 'critic'.
    """
    from app.orchestrator.state import CopilotState
    from app.orchestrator.supervisor import _dispatch_route

    # Create a mock state with next_agent == "application"
    state: CopilotState = {
        "user_id": "test_user",
        "thread_id": "test_thread",
        "user_message": "Test message",
        "plan": [],
        "next_agent": "application",
    }
    
    # _dispatch_route should return "application_send"
    result = _dispatch_route(state)
    assert result == "application_send", (
        f"Expected _dispatch_route to return 'application_send' when next_agent='application', "
        f"but got '{result}'"
    )

# ---------------------------------------------------------------------------
# Live gate (requires INFRA_UP=1)
# ---------------------------------------------------------------------------

_INFRA_UP = os.getenv("INFRA_UP") == "1"


@pytest.mark.skipif(not _INFRA_UP, reason="INFRA_UP not set — skipping live infra test")
def test_market_only_run():
    """Invoke a thread that routes to ``market`` only.

    Asserts:
    - At least one checkpoint was written.
    - ``final_answer`` is present in the output state.
    """
    from app.memory.checkpointer import checkpointer_cm
    from app.orchestrator.supervisor import build_supervisor

    with checkpointer_cm() as cp:
        graph = build_supervisor(checkpointer=cp)

        thread_id = "test-market-only-thread"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "user_id": "test_user",
            "thread_id": thread_id,
            "user_message": "What are the latest market trends for Python developers?",
            "uploaded_doc_ids": [],
        }

        result = graph.invoke(initial_state, config=config)

        # Must have produced a final answer
        assert result.get("final_answer"), (
            f"Expected 'final_answer' to be set, got: {result.get('final_answer')!r}"
        )

        # Checkpoint must have been written
        checkpoints = list(cp.list(config))
        assert len(checkpoints) >= 1, (
            f"Expected at least one checkpoint for thread '{thread_id}', got 0"
        )
