"""
Orchestrates the full CV analysis pipeline:
  1. Extract raw text (PDF/DOCX/pasted text, with OCR fallback)
  2. Structural extraction (spaCy NER + regex: name, contact info, orgs, sections)
  3. ATS scoring (deterministic rules engine)
  4. LLM feedback (LLM: skills, job titles, strengths/weaknesses, suggestions,
     and JD-alignment notes in tailored mode)
  5. Assemble into the CVAnalysisResponse contract
"""

from app.agents.cv_analysis.core.analysis import llm_feedback
from app.agents.cv_analysis.core.analysis.ats_scoring import score_ats
from app.agents.cv_analysis.core.extraction.parser import extract_text
from app.agents.cv_analysis.core.extraction.structure import detect_sections, extract_entities
from app.agents.cv_analysis.schemas import (
    CVAnalysisResponse,
    ExtractedEntities,
    LLMFeedback,
)


def _build_entities(base: ExtractedEntities, llm_output: llm_feedback._LLMOutput) -> ExtractedEntities:
    """Merge spaCy/regex-derived entities with LLM-derived skills/job_titles."""
    return ExtractedEntities(
        full_name=base.full_name,
        emails=base.emails,
        phones=base.phones,
        skills=llm_output.skills,
        organizations=base.organizations,
        job_titles=llm_output.job_titles,
    )


def run_standalone_analysis(
    *,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    raw_text: str | None = None,
) -> CVAnalysisResponse:
    cleaned_text = extract_text(file_bytes=file_bytes, filename=filename, raw_text=raw_text)

    base_entities = extract_entities(cleaned_text)
    sections = detect_sections(cleaned_text)

    ats = score_ats(
        cleaned_text=cleaned_text,
        has_email=bool(base_entities.emails),
        has_phone=bool(base_entities.phones),
        detected_sections=sections,
    )

    llm_result = llm_feedback.analyze_standalone(cleaned_text)
    entities = _build_entities(base_entities, llm_result)

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
    cleaned_text = extract_text(file_bytes=file_bytes, filename=filename, raw_text=raw_text)

    base_entities = extract_entities(cleaned_text)
    sections = detect_sections(cleaned_text)

    ats = score_ats(
        cleaned_text=cleaned_text,
        has_email=bool(base_entities.emails),
        has_phone=bool(base_entities.phones),
        detected_sections=sections,
    )

    llm_result = llm_feedback.analyze_tailored(cleaned_text, job_description)
    entities = _build_entities(base_entities, llm_result)

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
