import os

from app.core.tracing import configure_tracing


def test_configure_tracing_sets_project(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    configure_tracing()
    assert os.environ["LANGCHAIN_PROJECT"] == "career-copilot"
