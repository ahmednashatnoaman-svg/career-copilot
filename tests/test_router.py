"""Tests for app.orchestrator.router — TDD RED → GREEN."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.orchestrator.router import RoutingDecision, route
from app.orchestrator.state import CopilotState


def _make_state(**kwargs) -> CopilotState:
    defaults: CopilotState = {
        "user_id": "u1",
        "thread_id": "t1",
        "user_message": "test",
        "uploaded_doc_ids": [],
    }
    defaults.update(kwargs)
    return defaults


def _stub_llm(plan: list[str], rationale: str = "stubbed") -> MagicMock:
    """Return a mock that mimics get_llm("fast").with_structured_output(...).invoke(...)."""
    decision = RoutingDecision(plan=plan, rationale=rationale)
    chain = MagicMock()
    chain.invoke.return_value = decision
    structured_llm = MagicMock()
    structured_llm.with_structured_output.return_value = chain
    return structured_llm


# ---------------------------------------------------------------------------
# Basic routing
# ---------------------------------------------------------------------------

class TestRouteBasic:
    def test_market_plan_sets_next_agent(self):
        """Stub returns ['market'] for 'find AI jobs' → next_agent='market'."""
        stub = _stub_llm(["market"])
        state = _make_state(user_message="find AI jobs")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"] == ["market"]
        assert result["next_agent"] == "market"

    def test_empty_plan_gives_none_next_agent(self):
        """Guard: empty plan → next_agent=None."""
        stub = _stub_llm([])
        state = _make_state(user_message="hello")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"] == []
        assert result["next_agent"] is None

    def test_multi_step_plan_next_agent_is_first(self):
        """next_agent is always plan[0]."""
        stub = _stub_llm(["rag", "coaching"])
        state = _make_state(user_message="help me prepare")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["next_agent"] == "rag"


# ---------------------------------------------------------------------------
# Guardrail: application keyword → application must be last
# ---------------------------------------------------------------------------

class TestApplicationGuardrail:
    def test_apply_keyword_adds_application_last(self):
        """'apply to this job' with stub lacking application → application appended last."""
        stub = _stub_llm(["market", "matching"])
        state = _make_state(user_message="apply to this job")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert "application" in result["plan"]
        assert result["plan"][-1] == "application"

    def test_application_keyword_also_triggers_guardrail(self):
        """'send application' triggers same guardrail."""
        stub = _stub_llm(["coaching"])
        state = _make_state(user_message="send application for me")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"][-1] == "application"

    def test_application_already_last_not_duplicated(self):
        """If stub already returns application last, it should not be duplicated."""
        stub = _stub_llm(["matching", "application"])
        state = _make_state(user_message="apply now")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"].count("application") == 1
        assert result["plan"][-1] == "application"

    def test_application_not_last_in_stub_is_moved(self):
        """If stub places application in the middle, guardrail moves it to the end."""
        stub = _stub_llm(["application", "coaching"])
        state = _make_state(user_message="I want to apply")

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"][-1] == "application"
        assert result["plan"].count("application") == 1


# ---------------------------------------------------------------------------
# Guardrail: uploaded docs → cv_analysis must be first
# ---------------------------------------------------------------------------

class TestCvAnalysisGuardrail:
    def test_uploaded_docs_prepends_cv_analysis(self):
        """uploaded_doc_ids present + stub plan lacking cv_analysis → cv_analysis prepended."""
        stub = _stub_llm(["market"])
        state = _make_state(
            user_message="find jobs matching my profile",
            uploaded_doc_ids=["doc-123"],
        )

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"][0] == "cv_analysis"

    def test_cv_analysis_not_duplicated_if_already_present(self):
        """If stub already returns cv_analysis, it's not duplicated."""
        stub = _stub_llm(["cv_analysis", "market"])
        state = _make_state(
            user_message="analyze my cv",
            uploaded_doc_ids=["doc-abc"],
        )

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"].count("cv_analysis") == 1
        assert result["plan"][0] == "cv_analysis"

    def test_no_docs_does_not_prepend_cv_analysis(self):
        """Empty uploaded_doc_ids → cv_analysis NOT prepended when absent from stub."""
        stub = _stub_llm(["market"])
        state = _make_state(user_message="find jobs", uploaded_doc_ids=[])

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"] == ["market"]


# ---------------------------------------------------------------------------
# Guardrail combination: docs + apply keyword
# ---------------------------------------------------------------------------

class TestCombinedGuardrails:
    def test_docs_and_apply_keyword(self):
        """Both guardrails active: cv_analysis first, application last."""
        stub = _stub_llm(["market", "matching"])
        state = _make_state(
            user_message="apply to these jobs using my CV",
            uploaded_doc_ids=["doc-1"],
        )

        with patch("app.orchestrator.router.get_llm", return_value=stub):
            result = route(state)

        assert result["plan"][0] == "cv_analysis"
        assert result["plan"][-1] == "application"
