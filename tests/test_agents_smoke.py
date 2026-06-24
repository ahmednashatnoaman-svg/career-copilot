"""Smoke tests for agent subgraphs — no network calls."""


def test_market_graph_compiles():
    from app.agents.market_research.graph import market_agent_graph

    assert market_agent_graph is not None
    # compiled graph exposes get_graph()
    assert market_agent_graph.get_graph().nodes
