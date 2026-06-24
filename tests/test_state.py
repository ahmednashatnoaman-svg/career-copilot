"""Tests for CopilotState — TDD RED → GREEN."""

import operator
import typing

import pytest
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from app.orchestrator.state import CopilotState, HitlRequest

# ---------------------------------------------------------------------------
# HitlRequest tests
# ---------------------------------------------------------------------------

class TestHitlRequest:
    def test_valid_kinds(self):
        for kind in ("application_send", "critic_escalation", "shortlist_approval"):
            hr = HitlRequest(kind=kind, payload={"k": "v"}, prompt="Are you sure?")
            assert hr.kind == kind

    def test_invalid_kind_raises(self):
        with pytest.raises(ValidationError):
            HitlRequest(kind="unknown", payload={}, prompt="x")

    def test_fields_present(self):
        hr = HitlRequest(kind="application_send", payload={"a": 1}, prompt="Send?")
        assert hr.payload == {"a": 1}
        assert hr.prompt == "Send?"


# ---------------------------------------------------------------------------
# CopilotState annotation tests
# ---------------------------------------------------------------------------

class TestCopilotStateAnnotations:
    """Use __annotations__ + typing.get_args to inspect Annotated metadata."""

    def _raw_annotations(self) -> dict:
        # __annotations__ preserves Annotated wrappers; get_type_hints may strip them
        # in some Python versions without include_extras, so we combine both.
        raw = CopilotState.__annotations__
        return raw

    def test_messages_has_add_messages_reducer(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        ann = hints.get("messages") or self._raw_annotations().get("messages")
        args = typing.get_args(ann)
        assert add_messages in args, (
            f"Expected add_messages in Annotated args for 'messages', got {args}"
        )

    def test_evidence_has_operator_add_reducer(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        ann = hints.get("evidence") or self._raw_annotations().get("evidence")
        args = typing.get_args(ann)
        assert operator.add in args, (
            f"Expected operator.add in Annotated args for 'evidence', got {args}"
        )

    def test_errors_has_operator_add_reducer(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        ann = hints.get("errors") or self._raw_annotations().get("errors")
        args = typing.get_args(ann)
        assert operator.add in args, (
            f"Expected operator.add in Annotated args for 'errors', got {args}"
        )

    def test_namespaced_agent_keys_exist(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        expected_keys = [
            "cv_analysis", "market", "rag", "coaching",
            "matching", "portfolio", "career_plan", "application",
        ]
        for key in expected_keys:
            assert key in hints, f"Missing namespaced key: {key}"

    def test_input_keys_exist(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        for key in ("user_id", "thread_id", "user_message", "uploaded_doc_ids"):
            assert key in hints, f"Missing input key: {key}"

    def test_routing_keys_exist(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        for key in ("plan", "next_agent"):
            assert key in hints, f"Missing routing key: {key}"

    def test_control_keys_exist(self):
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        for key in ("critic_verdict", "critic_retries", "hitl_request", "final_answer"):
            assert key in hints, f"Missing control key: {key}"

    def test_namespaced_keys_are_plain_dicts_not_annotated(self):
        """Agent output keys must be plain (overwrite-safe) — no reducers."""
        hints = typing.get_type_hints(CopilotState, include_extras=True)
        plain_keys = [
            "cv_analysis", "market", "rag", "coaching",
            "matching", "portfolio", "career_plan", "application",
        ]
        for key in plain_keys:
            ann = hints[key]
            # If it's Annotated, get_args returns the inner type + metadata
            args = typing.get_args(ann)
            # For a plain annotation (not Annotated), get_args returns ()
            assert args == () or not any(
                callable(a) and a in (add_messages, operator.add) for a in args
            ), f"Key '{key}' should be plain (no reducer), but got Annotated: {ann}"
