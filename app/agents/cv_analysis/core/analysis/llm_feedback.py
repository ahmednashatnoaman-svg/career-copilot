"""
LLM-driven analysis via Groq: skills/job-title extraction, strengths/
weaknesses, suggestions, and (in tailored mode) JD-alignment notes.

This is the one place in the agent that calls out to an LLM. Everything
upstream (extraction, structure, ATS scoring) is deterministic.
"""

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.llm.provider import get_llm


class _LLMOutput(BaseModel):
    """Schema we ask the LLM to fill in. Internal to this module."""

    full_name: str | None = None
    organizations: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    jd_alignment_notes: list[str] = Field(default_factory=list)


STANDALONE_SYSTEM_PROMPT = """You are an expert technical resume reviewer.
Given a candidate's resume text, analyze it and respond with ONLY a JSON object
(no markdown fences, no preamble) matching exactly this shape:

{
  "full_name": "...",
  "organizations": ["..."],
  "skills": ["..."],
  "job_titles": ["..."],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "suggestions": ["..."]
}

Guidelines:
- "full_name": the candidate's full name as it appears on the resume.
- "organizations": companies, schools, and institutions the candidate is or was affiliated with.
- "skills": concrete technical and professional skills evidenced in the resume
  (tools, languages, frameworks, methodologies). Normalize obvious synonyms
  (e.g. "ML" and "Machine Learning" -> "Machine Learning"). Infer skills clearly
  implied by described work, not just explicitly named ones.
- "job_titles": job titles the candidate has held, as written or lightly normalized.
- "strengths": specific, evidence-based strengths (cite what in the resume supports each).
- "weaknesses": specific, constructive gaps or weaknesses in how the resume is written
  or what it's missing (not a judgment of the person).
- "suggestions": concrete, actionable edits the candidate could make.
"""

TAILORED_SYSTEM_PROMPT = """You are an expert technical resume reviewer helping a
candidate tailor their resume to a specific job description.
Given a candidate's resume text AND a target job description, respond with ONLY
a JSON object (no markdown fences, no preamble) matching exactly this shape:

{
  "full_name": "...",
  "organizations": ["..."],
  "skills": ["..."],
  "job_titles": ["..."],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "suggestions": ["..."],
  "jd_alignment_notes": ["..."]
}

Guidelines:
- "full_name": the candidate's full name as it appears on the resume.
- "organizations": companies, schools, and institutions the candidate is or was affiliated with.
- "skills" and "job_titles": extracted from the RESUME only, same rules as standalone review.
- "strengths" / "weaknesses": evaluate the resume on its own merits as a document.
- "suggestions": concrete, actionable edits to the resume.
- "jd_alignment_notes": specific observations about how well the resume aligns with
  THIS job description — what matches well, what's missing or under-emphasized, and
  how to better surface relevant experience for this specific role. Be concrete
  (reference specific requirements from the job description).
- Do not invent information not supported by the resume text.
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_groq(*, system_prompt: str, user_content: str) -> _LLMOutput:
    llm = get_llm("reason", temperature=0.2)
    chain = llm.with_structured_output(_LLMOutput)
    return chain.invoke([
        ("system", system_prompt),
        ("human", user_content),
    ])


def analyze_standalone(resume_text: str) -> _LLMOutput:
    return _call_groq(
        system_prompt=STANDALONE_SYSTEM_PROMPT,
        user_content=f"RESUME:\n{resume_text}",
    )


def analyze_tailored(resume_text: str, job_description: str) -> _LLMOutput:
    return _call_groq(
        system_prompt=TAILORED_SYSTEM_PROMPT,
        user_content=f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_description}",
    )
