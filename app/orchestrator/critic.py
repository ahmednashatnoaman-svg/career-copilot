"""Critic / Judge node with bounded regenerate-or-escalate loop.

``critic_node`` invokes ``get_llm("reason").with_structured_output(CriticVerdict)``
to evaluate the latest draft against the retrieved evidence.  It ALWAYS increments
``critic_retries`` before checking the budget.  If the verdict is not grounded AND
the post-increment ``critic_retries > MAX_CRITIC_RETRIES`` the action is forced to
``"ESCALATE"`` — preventing an unbounded regeneration loop.

``critic_route`` reads ``critic_verdict["action"]`` and maps it to one of three
LangGraph edge labels: ``"accept"``, ``"regenerate"``, or ``"escalate"``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.llm.provider import get_llm
from app.orchestrator.state import CopilotState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CRITIC_RETRIES: int = 2

# ---------------------------------------------------------------------------
# Structured output model
# ---------------------------------------------------------------------------

_CRITIC_PROMPT = """\
You are a critical reviewer for an AI Career Copilot.

Your job is to assess whether the draft answer is grounded in the provided evidence.

Draft answer:
{draft}

Evidence (retrieved chunks / citations):
{evidence}

Return a JSON with:
  grounded – true if the draft is fully supported by the evidence, false otherwise
  issues   – list of specific issues (empty if grounded)
  action   – one of "ACCEPT" (grounded), "REGENERATE" (fixable), "ESCALATE" (unfixable)
"""


class CriticVerdict(BaseModel):
    """Structured output from the critic LLM."""

    grounded: bool
    issues: list[str]
    action: Literal["ACCEPT", "REGENERATE", "ESCALATE"]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def critic_node(state: CopilotState) -> dict:
    """Evaluate the latest draft and return updated state fields.

    Steps:
    1. Increment ``critic_retries`` (always, before the budget check).
    2. Ask the LLM to produce a ``CriticVerdict``.
    3. If ``not grounded`` and post-increment ``critic_retries > MAX_CRITIC_RETRIES``
       → force ``action = "ESCALATE"``.
    4. Return the updated keys: ``critic_retries``, ``critic_verdict``.
    """
    # --- 1. Increment retries before anything else ---------------------------
    current_retries: int = state.get("critic_retries") or 0
    new_retries: int = current_retries + 1

    # --- 2. Build context for the LLM ----------------------------------------
    # final_answer is only set by aggregate (which runs AFTER critic accepts).
    # On the first critic pass build a draft from the agent outputs themselves.
    draft: str = state.get("final_answer") or ""
    if not draft:
        preview_parts: list[str] = []
        if cv := state.get("cv_analysis"):
            preview_parts.append(f"[CV Analysis]\n{cv}")
        if rag_out := state.get("rag"):
            answer = rag_out.get("answer", "") if isinstance(rag_out, dict) else str(rag_out)
            if answer:
                preview_parts.append(f"[Knowledge Base]\n{answer}")
        if market_out := state.get("market"):
            preview_parts.append(f"[Market Research]\n{market_out}")
        if coaching_out := state.get("coaching"):
            response = (
                coaching_out.get("response", "") if isinstance(coaching_out, dict) else str(coaching_out)
            )
            if response:
                preview_parts.append(f"[Coaching]\n{response}")
        if app := state.get("application"):
            preview_parts.append(f"[Application]\n{app}")
        draft = "\n\n".join(preview_parts)

    # Nothing to review → auto-accept (aggregate will handle empty state message)
    if not draft.strip():
        return {
            "critic_retries": new_retries,
            "critic_verdict": CriticVerdict(
                grounded=True, issues=[], action="ACCEPT"
            ).model_dump(),
        }

    evidence: list[dict] = state.get("evidence") or []
    evidence_text = "\n".join(
        f"[{i + 1}] {chunk}" for i, chunk in enumerate(evidence)
    )

    prompt = _CRITIC_PROMPT.format(draft=draft, evidence=evidence_text)

    llm = get_llm("reason")
    chain = llm.with_structured_output(CriticVerdict)
    verdict: CriticVerdict = chain.invoke(prompt)

    # --- 3. Budget check: force ESCALATE if budget exceeded ------------------
    if not verdict.grounded and new_retries > MAX_CRITIC_RETRIES:
        verdict = CriticVerdict(
            grounded=verdict.grounded,
            issues=verdict.issues,
            action="ESCALATE",
        )

    # --- 4. Return updated state ---------------------------------------------
    return {
        "critic_retries": new_retries,
        "critic_verdict": verdict.model_dump(),
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

def critic_route(state: CopilotState) -> str:
    """Map the stored critic verdict (and retry budget) to a LangGraph edge label.

    Returns:
        ``"accept"``     – verdict action is ACCEPT
        ``"regenerate"`` – verdict action is REGENERATE
        ``"escalate"``   – verdict action is ESCALATE (routes to application_send if application exists, else aggregate)
    """
    verdict: dict | None = state.get("critic_verdict")
    if verdict is None:
        # Defensive fallback: no verdict stored → escalate
        return "escalate" if "application" in state.get("plan", []) else "accept"

    action: str = verdict.get("action", "ESCALATE")

    if action == "ACCEPT":
        return "accept"
    if action == "REGENERATE":
        return "regenerate"
    
    # If action is ESCALATE, we only want to HITL (application_send) if an application was drafted
    if "application" in state.get("plan", []):
        return "escalate"
    
    # Otherwise, it's a search/coaching escalation, just aggregate what we have
    return "accept"
