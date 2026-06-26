"""
Pydantic models defining the CV Analysis Agent's input/output contract.

This is the contract other agents (Job Matching, Skill Gap, Application Agent)
will depend on. Keep field names stable once other teams start consuming this.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedEntities(BaseModel):
    """Structural entities pulled from the resume via spaCy NER + section rules."""

    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)  # companies, schools
    job_titles: list[str] = Field(default_factory=list)


class ATSCheck(BaseModel):
    """Deterministic, rules-based ATS-friendliness score. Not LLM-guessed."""

    score: int = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    passed_checks: list[str] = Field(default_factory=list)


class LLMFeedback(BaseModel):
    """Judgment-based feedback produced by the LLM call."""

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    jd_alignment_notes: list[str] | None = None  # populated only in tailored mode


class CVAnalysisResponse(BaseModel):
    """Top-level response returned by both /analyze and /analyze/tailored."""

    cleaned_text: str
    entities: ExtractedEntities
    ats: ATSCheck
    feedback: LLMFeedback
    mode: Literal["standalone", "tailored"]
