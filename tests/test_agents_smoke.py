"""Smoke tests for agent subgraphs — no network calls."""


def test_market_graph_compiles():
    from app.agents.market_research.graph import market_agent_graph

    assert market_agent_graph is not None
    # compiled graph exposes get_graph()
    assert market_agent_graph.get_graph().nodes


def test_cv_node_importable():
    from app.agents.cv_analysis.integration.graph_node import cv_analysis_node
    assert callable(cv_analysis_node)


def test_cv_standalone_text(monkeypatch):
    from app.agents.cv_analysis.core import pipeline
    # stub the LLM feedback so the test needs no network
    monkeypatch.setattr(
        pipeline, "run_tailored_analysis", pipeline.run_tailored_analysis, raising=True
    )
    from app.agents.cv_analysis.integration.graph_node import cv_analysis_node
    monkeypatch.setattr(
        "app.agents.cv_analysis.core.analysis.llm_feedback.get_llm",
        lambda *a, **k: type("M", (), {"invoke": lambda self, p: type("R", (), {"content": '{"skills":[],"job_titles":[],"strengths":[],"weaknesses":[],"suggestions":[],"jd_alignment_notes":[]}'})()})(),
        raising=False,
    )
    out = cv_analysis_node({"resume_text": "Jane Doe. Python, FastAPI, LangGraph. 3 years backend."})
    assert "cv_analysis" in out
    assert out["cv_analysis"].entities is not None


def test_coaching_graph_builds():
    from app.agents.coaching.graph import build_coaching_graph
    g = build_coaching_graph(checkpointer=None)
    assert g.get_graph().nodes
