"""Supervisor router: classifies user intent and produces an ordered agent plan.

Uses ``get_llm("fast").with_structured_output(RoutingDecision)`` to produce an
initial plan, then applies deterministic guardrails:

- If the user message mentions "apply" or "application" →
  ``application`` is ensured to be present and placed **last**.
- If docs were uploaded and ``cv_analysis`` is not already in the plan →
  ``cv_analysis`` is **prepended** (runs first).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from app.llm.provider import get_llm
from app.memory.longterm import recall
from app.orchestrator.state import CopilotState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured output model
# ---------------------------------------------------------------------------

VALID_AGENTS = [
    "cv_analysis",
    "rag",
    "market",
    "matching",
    "coaching",
    "application",
]

_ROUTING_PROMPT = """\
You are the supervisor of an AI Career Copilot.  Given the user's message and \
context, decide which agents to invoke and in what order.

Available agents (use only names from this list):
- cv_analysis   : parse & analyse an uploaded CV / resume
- rag           : retrieve from the user's personal knowledge base
- market        : search job market / salary data / company info
- matching      : rank / match jobs or companies to the user's profile
- coaching      : career coaching, interview prep, skill gap analysis
- application   : draft / send a job application

Context:
- user_message: {user_message}
- uploaded_doc_ids (non-empty means CV was uploaded): {uploaded_doc_ids}
- long_term_memory (recalled user facts — may be empty): {long_term_memory}

Return a JSON object with:
  plan      – ordered list of agent names to invoke (subset of the list above)
  rationale – one-sentence explanation
"""


class RoutingDecision(BaseModel):
    """Structured output returned by the fast LLM."""

    plan: list[str]
    rationale: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def route(state: CopilotState) -> dict:
    """Classify user intent and return ``{"plan": [...], "next_agent": ...}``.

    The plan is built by:
    1. Asking the fast LLM for an initial structured decision.
    2. Applying deterministic guardrails on top of the LLM output.
    """
    user_message: str = state.get("user_message", "")
    uploaded_doc_ids: list[str] = state.get("uploaded_doc_ids") or []
    user_id: str = state.get("user_id") or ""

    # --- Recall long-term user facts (graceful: returns {} on any error) ---
    long_term_memory: dict = {}
    import os
    if user_id and os.getenv("DATABASE_URL"):
        try:
            long_term_memory = recall(user_id)
        except Exception:
            logger.warning("router: recall failed for user=%s — continuing without memory", user_id)

    # --- LLM call ----------------------------------------------------------
    llm = get_llm("fast")
    chain = llm.with_structured_output(RoutingDecision)

    prompt = _ROUTING_PROMPT.format(
        user_message=user_message,
        uploaded_doc_ids=uploaded_doc_ids,
        long_term_memory=long_term_memory or "(none)",
    )
    decision: RoutingDecision = chain.invoke(prompt)

    # Filter to only valid agent names (defensive)
    plan: list[str] = [a for a in decision.plan if a in VALID_AGENTS]

    # --- Guardrail 1: application keyword → application must be LAST -------
    msg_lower = user_message.lower()
    if "apply" in msg_lower or "application" in msg_lower:
        # Remove any existing occurrence then append at the end
        plan = [a for a in plan if a != "application"]
        plan.append("application")

    # --- Guardrail 2: docs uploaded + cv_analysis absent → prepend ----------
    if uploaded_doc_ids and "cv_analysis" not in plan:
        plan.insert(0, "cv_analysis")

    # --- Build return dict --------------------------------------------------
    next_agent: str | None = plan[0] if plan else None

    return {"plan": plan, "next_agent": next_agent}
