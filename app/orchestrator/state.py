"""Shared LangGraph state for the AI Career Copilot Supervisor graph."""

from __future__ import annotations

from operator import add
from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class HitlRequest(BaseModel):
    """Payload sent to the human-in-the-loop pause node."""

    kind: Literal["application_send", "critic_escalation", "shortlist_approval"]
    payload: dict
    prompt: str


class CopilotState(TypedDict, total=False):
    # --- inputs ---
    user_id: str
    thread_id: str
    user_message: str
    uploaded_doc_ids: list[str]

    # --- routing ---
    plan: list[str]          # ordered agent names to run
    next_agent: str | None

    # --- namespaced agent outputs (overwrite-safe, one key per agent) ---
    cv_analysis: dict
    market: dict
    rag: dict
    coaching: dict
    matching: dict
    portfolio: dict
    career_plan: dict
    application: dict

    # --- accumulators (reducer-annotated) ---
    messages: Annotated[list, add_messages]
    evidence: Annotated[list[dict], add]   # retrieved chunks / citations
    errors: Annotated[list[str], add]

    # --- control ---
    critic_verdict: dict | None
    critic_retries: int
    hitl_request: HitlRequest | None
    final_answer: str | None
