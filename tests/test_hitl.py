"""Tests for app.orchestrator.hitl — TDD RED → GREEN."""

from __future__ import annotations

from unittest.mock import patch

from app.orchestrator.hitl import application_send_node, request_approval
from app.orchestrator.state import CopilotState, HitlRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> CopilotState:
    defaults: CopilotState = {
        "user_id": "u1",
        "thread_id": "t1",
        "user_message": "Apply to Acme Corp",
        "application": {
            "job_title": "Software Engineer",
            "company": "Acme Corp",
            "cover_letter": "Dear Hiring Manager…",
            "status": "draft",
        },
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# request_approval — unit tests
# ---------------------------------------------------------------------------

class TestRequestApproval:
    def test_calls_interrupt_with_expected_structure(self):
        canned = {"approved": True, "notes": "LGTM"}
        with patch("app.orchestrator.hitl.interrupt", return_value=canned) as mock_intr:
            result = request_approval(
                kind="application_send",
                payload={"foo": "bar"},
                prompt="Approve?",
            )
        mock_intr.assert_called_once()
        call_arg = mock_intr.call_args[0][0]
        assert call_arg["kind"] == "application_send"
        assert call_arg["payload"] == {"foo": "bar"}
        assert call_arg["prompt"] == "Approve?"
        assert result == canned

    def test_returns_resume_value(self):
        resume = {"approved": False, "reason": "Not a good fit"}
        with patch("app.orchestrator.hitl.interrupt", return_value=resume):
            result = request_approval("application_send", {}, "Review?")
        assert result == resume


# ---------------------------------------------------------------------------
# application_send_node — approval path
# ---------------------------------------------------------------------------

class TestApplicationSendNodeApproval:
    def test_approval_sets_status_approved(self):
        state = _make_state()
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": True}):
            output = application_send_node(state)

        assert "application" in output
        assert output["application"]["status"] == "APPROVED"

    def test_approval_preserves_other_fields(self):
        state = _make_state()
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": True}):
            output = application_send_node(state)

        app = output["application"]
        assert app["job_title"] == "Software Engineer"
        assert app["company"] == "Acme Corp"

    def test_approval_sets_hitl_request(self):
        state = _make_state()
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": True}):
            output = application_send_node(state)

        assert "hitl_request" in output
        req = output["hitl_request"]
        assert isinstance(req, HitlRequest)
        assert req.kind == "application_send"


# ---------------------------------------------------------------------------
# application_send_node — rejection path
# ---------------------------------------------------------------------------

class TestApplicationSendNodeRejection:
    def test_rejection_sets_status_rejected(self):
        state = _make_state()
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": False}):
            output = application_send_node(state)

        assert output["application"]["status"] == "REJECTED"

    def test_rejection_preserves_other_fields(self):
        state = _make_state()
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": False}):
            output = application_send_node(state)

        assert output["application"]["company"] == "Acme Corp"


# ---------------------------------------------------------------------------
# application_send_node — edge cases
# ---------------------------------------------------------------------------

class TestApplicationSendNodeEdgeCases:
    def test_missing_application_key_does_not_raise(self):
        state: CopilotState = {
            "user_id": "u1",
            "thread_id": "t1",
            "user_message": "hi",
        }
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": True}):
            output = application_send_node(state)  # must not KeyError

        assert "application" in output
        assert output["application"]["status"] == "APPROVED"

    def test_empty_application_dict_does_not_raise(self):
        state = _make_state(application={})
        with patch("app.orchestrator.hitl.interrupt", return_value={"approved": False}):
            output = application_send_node(state)

        assert output["application"]["status"] == "REJECTED"
