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

    # --- input data fields (populated at run start) ---
    resume_text: str          # Raw text of CV/resume
    resume_filename: str      # Original filename
    resume_file_bytes: bytes | None  # Raw bytes if needed by agents
    github_username: str      # GitHub username for portfolio agent
    github_token: str         # GitHub token (optional)
    job_description: str      # Target job description (optional, for tailoring)

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
    hitl_request: dict | None  # stored as plain dict (Pydantic fails msgpack)
    final_answer: str | None
