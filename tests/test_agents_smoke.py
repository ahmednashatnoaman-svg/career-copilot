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


def test_rag_node_returns_grounded_answer_with_citations(monkeypatch):
    """RED: rag_node retrieves evidence and returns grounded answer with citations."""
    from app.agents.rag.agent import rag_node
    from app.orchestrator.state import CopilotState

    # Monkeypatch retrieve to return 2 canned hits
    canned_hits = [
        {
            "text": "Python is a high-level programming language.",
            "score": 0.95,
            "doc_id": "doc_1",
            "source": "rag",
        },
        {
            "text": "FastAPI is a modern web framework for Python.",
            "score": 0.85,
            "doc_id": "doc_2",
            "source": "rag",
        },
    ]
    monkeypatch.setattr(
        "app.agents.rag.agent.retrieve",
        lambda user_id, query: canned_hits,
        raising=True,
    )

    # Monkeypatch get_llm to return a stub LLM
    stub_llm = type("StubLLM", (), {
        "invoke": lambda self, prompt: type("Response", (), {
            "content": "Based on the documents, Python is a high-level language and FastAPI is a modern web framework."
        })()
    })()
    monkeypatch.setattr(
        "app.agents.rag.agent.get_llm",
        lambda task: stub_llm,
        raising=True,
    )

    # Create input state
    state = CopilotState(
        user_id="user_123",
        user_message="Tell me about Python and FastAPI",
    )

    # Call rag_node
    result = rag_node(state)

    # Assertions
    assert "rag" in result
    assert "answer" in result["rag"]
    assert len(result["rag"]["answer"]) > 0
    assert "citations" in result["rag"]
    assert isinstance(result["rag"]["citations"], list)
    assert "evidence" in result
    assert len(result["evidence"]) == 2
    assert result["evidence"][0]["doc_id"] == "doc_1"
    assert result["evidence"][1]["doc_id"] == "doc_2"
