"""
Orchestrates the full CV analysis pipeline:
  1. Extract raw text (PDF/DOCX/pasted text, with OCR fallback)
  2. Structural extraction (regex: contact info, section headers)
  3. ATS scoring (deterministic rules engine)
  4. LLM feedback (Groq: full name, organizations, skills, job titles,
     strengths/weaknesses, suggestions, and JD-alignment notes in tailored mode)
  5. Assemble into the CVAnalysisResponse contract

Note: full_name, organizations, skills, and job_titles are all derived from
the LLM step, not from NER. spaCy was tried for full_name/organizations but
performed poorly on resume text in practice (out-of-distribution formatting
that general-purpose NER wasn't trained for) — the LLM has actual resume
context to reason with, so all four entity fields now come from there.
"""

from app.core.analysis import llm_feedback
from app.core.analysis.ats_scoring import score_ats
from app.core.extraction.parser import extract_text
from app.core.extraction.structure import detect_sections, extract_emails, extract_phones
from app.schemas import ATSCheck, CVAnalysisResponse, ExtractedEntities, LLMFeedback


def _build_entities(
    llm_output: llm_feedback._LLMOutput,
    emails: list[str],
    phones: list[str],
) -> ExtractedEntities:
    """Contact info comes from regex; everything else comes from the LLM."""
    return ExtractedEntities(
        full_name=llm_output.full_name,
        emails=emails,
        phones=phones,
        skills=llm_output.skills,
        organizations=llm_output.organizations,
        job_titles=llm_output.job_titles,
    )


def _extract_and_score(
    *,
    file_bytes: bytes | None,
    filename: str | None,
    raw_text: str | None,
) -> tuple[str, list[str], list[str], ATSCheck]:
    """
    Shared first half of both analysis modes: extract text, pull contact
    info via regex, detect sections, and compute the ATS score. Identical
    regardless of standalone vs. tailored mode.
    """
    cleaned_text = extract_text(file_bytes=file_bytes, filename=filename, raw_text=raw_text)

    emails = extract_emails(cleaned_text)
    phones = extract_phones(cleaned_text)
    sections = detect_sections(cleaned_text)

    ats = score_ats(
        cleaned_text=cleaned_text,
        has_email=bool(emails),
        has_phone=bool(phones),
        detected_sections=sections,
    )

    return cleaned_text, emails, phones, ats


def run_standalone_analysis(
    *,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    raw_text: str | None = None,
) -> CVAnalysisResponse:
    cleaned_text, emails, phones, ats = _extract_and_score(
        file_bytes=file_bytes, filename=filename, raw_text=raw_text
    )

    llm_result = llm_feedback.analyze_standalone(cleaned_text)
    entities = _build_entities(llm_result, emails, phones)

    feedback = LLMFeedback(
        strengths=llm_result.strengths,
        weaknesses=llm_result.weaknesses,
        suggestions=llm_result.suggestions,
        jd_alignment_notes=None,
    )

    return CVAnalysisResponse(
        cleaned_text=cleaned_text,
        entities=entities,
        ats=ats,
        feedback=feedback,
        mode="standalone",
    )


def run_tailored_analysis(
    *,
    job_description: str,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    raw_text: str | None = None,
) -> CVAnalysisResponse:
    cleaned_text, emails, phones, ats = _extract_and_score(
        file_bytes=file_bytes, filename=filename, raw_text=raw_text
    )

    llm_result = llm_feedback.analyze_tailored(cleaned_text, job_description)
    entities = _build_entities(llm_result, emails, phones)

    feedback = LLMFeedback(
        strengths=llm_result.strengths,
        weaknesses=llm_result.weaknesses,
        suggestions=llm_result.suggestions,
        jd_alignment_notes=llm_result.jd_alignment_notes,
    )

    return CVAnalysisResponse(
        cleaned_text=cleaned_text,
        entities=entities,
        ats=ats,
        feedback=feedback,
        mode="tailored",
    )