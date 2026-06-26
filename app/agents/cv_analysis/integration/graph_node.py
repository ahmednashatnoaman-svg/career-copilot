"""
Integration adapter for the Supervisor Agent's LangGraph orchestration.

This module is the ONLY integration surface other agents/the Supervisor
should depend on. Everything in app/core/ (pipeline.py, extraction/, and
analysis/) is an internal implementation detail and may change without notice — this
adapter's function signature and state contract are what's stable.

Why this exists separately from pipeline.py:
  pipeline.py is a plain Python workflow (no LangGraph, no agentic
  branching — see project discussion). The Supervisor, however, IS a
  LangGraph agent and needs each sub-agent to behave like a graph node:
  accept the shared graph state, return a partial state update. This
  module is that thin shim — it does not change how the CV workflow works
  internally, only how it's called.

Usage from the Supervisor's graph:

    from app.integration.graph_node import cv_analysis_node, CVAnalysisInputState

    graph.add_node("cv_analysis", cv_analysis_node)
"""

from typing import TypedDict

from app.core.pipeline import run_standalone_analysis, run_tailored_analysis
from app.schemas import CVAnalysisResponse


class CVAnalysisInputState(TypedDict, total=False):
    """
    The subset of shared graph state this node reads.

    Exactly one of (`resume_file_bytes` + `resume_filename`) or `resume_text`
    must be present — same input contract as the FastAPI endpoints, just
    delivered via state instead of an HTTP request.

    `job_description` is optional: present -> tailored mode, absent -> standalone.
    """

    resume_file_bytes: bytes | None
    resume_filename: str | None
    resume_text: str | None
    job_description: str | None


class CVAnalysisOutputState(TypedDict):
    """
    The partial state update this node returns. Nested under one key
    (`cv_analysis`) per team agreement, so it doesn't collide with other
    agents' top-level state keys.
    """

    cv_analysis: CVAnalysisResponse


def cv_analysis_node(state: CVAnalysisInputState) -> CVAnalysisOutputState:
    """
    LangGraph-node-shaped entry point. Pure function: reads known keys from
    `state`, returns a partial update — exactly what LangGraph expects a
    node callable to do. Add this directly to the Supervisor's StateGraph.

    Raises the same exceptions as the underlying pipeline (e.g.
    UnsupportedFileTypeError, OcrUnavailableError, ValueError for missing
    input) — the Supervisor is responsible for catching/handling those the
    same way it would for any other node failure.
    """
    job_description = state.get("job_description")

    if job_description:
        response = run_tailored_analysis(
            job_description=job_description,
            file_bytes=state.get("resume_file_bytes"),
            filename=state.get("resume_filename"),
            raw_text=state.get("resume_text"),
        )
    else:
        response = run_standalone_analysis(
            file_bytes=state.get("resume_file_bytes"),
            filename=state.get("resume_filename"),
            raw_text=state.get("resume_text"),
        )

    return {"cv_analysis": response}
