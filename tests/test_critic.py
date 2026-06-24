"""Tests for app.orchestrator.critic — TDD RED → GREEN.

Three cases:
  (a) grounded verdict → critic_route == "accept"
  (b) ungrounded, retries start 0 → after critic_node, critic_retries incremented AND
      critic_route == "regenerate"
  (c) ungrounded, retries already AT budget (==MAX_CRITIC_RETRIES) →
      critic_node forces ESCALATE and critic_route == "escalate"
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.orchestrator.critic import (
    MAX_CRITIC_RETRIES,
    CriticVerdict,
    critic_node,
    critic_route,
)
from app.orchestrator.state import CopilotState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> CopilotState:
    defaults: CopilotState = {
        "user_id": "u1",
        "thread_id": "t1",
        "final_answer": "The answer is 42.",
        "evidence": [{"text": "source doc", "score": 0.9}],
        "critic_retries": 0,
    }
    defaults.update(kwargs)
    return defaults


def _stub_llm(verdict: CriticVerdict) -> MagicMock:
    """Return a mock mimicking get_llm("reason").with_structured_output(...).invoke(...)."""
    chain = MagicMock()
    chain.invoke.return_value = verdict
    llm = MagicMock()
    llm.with_structured_output.return_value = chain
    return llm


# ---------------------------------------------------------------------------
# (a) Grounded verdict → accept
# ---------------------------------------------------------------------------

class TestCriticGrounded:
    def test_grounded_verdict_routes_to_accept(self):
        """When LLM returns grounded=True, critic_route should return 'accept'."""
        verdict = CriticVerdict(grounded=True, issues=[], action="ACCEPT")
        stub = _stub_llm(verdict)
        state = _make_state()

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        # Merge updated state for routing check
        merged = {**state, **updated}
        assert critic_route(merged) == "accept"

    def test_grounded_verdict_stores_verdict_in_state(self):
        """critic_node should store the verdict dict in the returned state."""
        verdict = CriticVerdict(grounded=True, issues=[], action="ACCEPT")
        stub = _stub_llm(verdict)
        state = _make_state()

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        assert updated["critic_verdict"] is not None
        stored = updated["critic_verdict"]
        assert stored["grounded"] is True
        assert stored["action"] == "ACCEPT"


# ---------------------------------------------------------------------------
# (b) Ungrounded, retries=0 → regenerate and increment
# ---------------------------------------------------------------------------

class TestCriticUngroundedLowRetries:
    def test_ungrounded_retries_incremented(self):
        """Starting at retries=0, after critic_node, critic_retries should be 1."""
        verdict = CriticVerdict(grounded=False, issues=["hallucination"], action="REGENERATE")
        stub = _stub_llm(verdict)
        state = _make_state(critic_retries=0)

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        assert updated["critic_retries"] == 1

    def test_ungrounded_below_budget_routes_to_regenerate(self):
        """retries=0 (below MAX_CRITIC_RETRIES=2), ungrounded → 'regenerate'."""
        verdict = CriticVerdict(grounded=False, issues=["hallucination"], action="REGENERATE")
        stub = _stub_llm(verdict)
        state = _make_state(critic_retries=0)

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        merged = {**state, **updated}
        assert critic_route(merged) == "regenerate"

    def test_ungrounded_at_max_retries_still_regenerates(self):
        """retries=1 → post-increment=2 == MAX_CRITIC_RETRIES → still 'regenerate'.

        The escalation condition is post_retries > MAX (strict greater-than), so
        reaching exactly MAX on this attempt still allows one more try (the 3rd attempt
        with pre-retries=2 will post-increment to 3>2 and force ESCALATE).
        """
        verdict = CriticVerdict(grounded=False, issues=["bad ref"], action="REGENERATE")
        stub = _stub_llm(verdict)
        state = _make_state(critic_retries=1)

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        # Post-increment: retries becomes 2 == MAX_CRITIC_RETRIES (not > MAX) → regenerate
        assert updated["critic_retries"] == 2
        merged = {**state, **updated}
        assert critic_route(merged) == "regenerate"
        assert updated["critic_verdict"]["action"] == "REGENERATE"


# ---------------------------------------------------------------------------
# (c) Ungrounded, retries already AT budget → escalate (boundary case)
# ---------------------------------------------------------------------------

class TestCriticBoundaryEscalate:
    def test_ungrounded_at_budget_forces_escalate(self):
        """retries==MAX_CRITIC_RETRIES before node runs → post-increment exceeds budget → ESCALATE."""
        # LLM wants to REGENERATE but budget is exhausted
        verdict = CriticVerdict(grounded=False, issues=["still wrong"], action="REGENERATE")
        stub = _stub_llm(verdict)
        # Start at MAX so post-increment == MAX+1 > MAX
        state = _make_state(critic_retries=MAX_CRITIC_RETRIES)

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        assert updated["critic_verdict"]["action"] == "ESCALATE"
        merged = {**state, **updated}
        assert critic_route(merged) == "escalate"

    def test_ungrounded_at_budget_retries_still_incremented(self):
        """Even when escalating due to budget, critic_retries is incremented."""
        verdict = CriticVerdict(grounded=False, issues=["nope"], action="REGENERATE")
        stub = _stub_llm(verdict)
        state = _make_state(critic_retries=MAX_CRITIC_RETRIES)

        with patch("app.orchestrator.critic.get_llm", return_value=stub):
            updated = critic_node(state)

        assert updated["critic_retries"] == MAX_CRITIC_RETRIES + 1

    def test_max_critic_retries_is_two(self):
        """Sanity: MAX_CRITIC_RETRIES == 2 as specified."""
        assert MAX_CRITIC_RETRIES == 2

    def test_third_failed_attempt_escalates_not_fourth(self):
        """With MAX=2: attempt #1 (0→1) regenerate, #2 (1→2) regenerate, #3 (2→3) escalate.

        The condition is post_retries > MAX_CRITIC_RETRIES (strict), so:
          - Attempt 1: pre=0, post=1, 1>2 false → regenerate
          - Attempt 2: pre=1, post=2, 2>2 false → regenerate
          - Attempt 3: pre=2, post=3, 3>2 true  → ESCALATE (no 4th loop)
        """
        regenerate_verdict = CriticVerdict(grounded=False, issues=["bad"], action="REGENERATE")

        # Attempt 1: retries=0 → post-increment=1 (< MAX=2) → regenerate
        stub1 = _stub_llm(regenerate_verdict)
        state1 = _make_state(critic_retries=0)
        with patch("app.orchestrator.critic.get_llm", return_value=stub1):
            out1 = critic_node(state1)
        assert out1["critic_retries"] == 1
        merged1 = {**state1, **out1}
        assert critic_route(merged1) == "regenerate"

        # Attempt 2: retries=1 → post-increment=2 (== MAX=2, not > MAX) → still regenerate
        stub2 = _stub_llm(regenerate_verdict)
        state2 = {**state1, **out1}
        with patch("app.orchestrator.critic.get_llm", return_value=stub2):
            out2 = critic_node(state2)
        assert out2["critic_retries"] == 2
        merged2 = {**state2, **out2}
        assert critic_route(merged2) == "regenerate"

        # Attempt 3: retries=2 → post-increment=3 (3 > MAX=2) → ESCALATE
        stub3 = _stub_llm(regenerate_verdict)
        state3 = {**state2, **out2}
        with patch("app.orchestrator.critic.get_llm", return_value=stub3):
            out3 = critic_node(state3)
        assert out3["critic_retries"] == 3
        merged3 = {**state3, **out3}
        assert critic_route(merged3) == "escalate"
        assert out3["critic_verdict"]["action"] == "ESCALATE"
