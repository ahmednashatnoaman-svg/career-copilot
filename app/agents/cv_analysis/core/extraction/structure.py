"""
Structural extraction from cleaned resume text: entities (names, orgs, dates)
via spaCy NER, plus regex-based extraction for things spaCy doesn't reliably
catch (emails, phone numbers) and simple section header detection.

This module is deliberately deterministic — no LLM calls here. Anything
requiring judgment belongs in core/analysis/llm_feedback.py.
"""

import re

import spacy
from spacy.language import Language

from app.agents.cv_analysis.schemas import ExtractedEntities

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Matches common phone formats: +20 100 123 4567, (123) 456-7890, 123-456-7890, etc.
PHONE_PATTERN = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}"
)

# Common resume section headers, used for lightweight section splitting.
SECTION_HEADERS = [
    "summary",
    "objective",
    "experience",
    "work experience",
    "employment history",
    "education",
    "skills",
    "technical skills",
    "projects",
    "certifications",
    "publications",
    "languages",
    "awards",
    "references",
]

_nlp: Language | None = None
_nlp_available: bool | None = None  # None = not yet tried


def get_nlp() -> Language | None:
    """
    Lazily load the spaCy model once and reuse it.

    Falls back to None (rule-based-only extraction) if no model is available.
    Download with: uv run python -m spacy download en_core_web_md
    """
    global _nlp, _nlp_available
    if _nlp_available is None:
        for model_name in ("en_core_web_md", "en_core_web_sm"):
            try:
                _nlp = spacy.load(model_name)
                _nlp_available = True
                break
            except OSError:
                continue
        else:
            import warnings
            warnings.warn(
                "No spaCy model found (tried en_core_web_md, en_core_web_sm). "
                "NER-based extraction disabled; falling back to regex-only. "
                "Install with: uv run python -m spacy download en_core_web_sm",
                RuntimeWarning,
                stacklevel=2,
            )
            _nlp_available = False
    return _nlp


def extract_emails(text: str) -> list[str]:
    return sorted(set(EMAIL_PATTERN.findall(text)))


# A bare two-year range like "2018-2022" or "2018–2022" — common in resume
# date ranges — has 8 digits and would otherwise pass the phone digit-count
# filter. Exclude this specific shape explicitly.
_YEAR_RANGE_PATTERN = re.compile(r"^(19|20)\d{2}[\s.\-–—]+(19|20)\d{2}$")


def extract_phones(text: str) -> list[str]:
    full_matches = [m.group() for m in PHONE_PATTERN.finditer(text)]
    cleaned = []
    for m in full_matches:
        stripped = m.strip()
        digit_count = len(re.sub(r"\D", "", stripped))
        if digit_count < 7:
            continue  # too short to plausibly be a phone number
        if _YEAR_RANGE_PATTERN.match(stripped):
            continue  # e.g. "2018-2022" — a date range, not a phone number
        cleaned.append(stripped)
    return sorted(set(cleaned))


def detect_sections(text: str) -> dict[str, str]:
    """
    Naive section splitter: finds lines that match known section headers
    (case-insensitive, standalone line) and splits the text accordingly.
    Returns a dict of {section_name: section_text}.
    """
    lines = text.splitlines()
    sections: dict[str, list[str]] = {}
    current_section = "header"  # text before the first recognized section
    sections[current_section] = []

    for line in lines:
        stripped = line.strip().lower().rstrip(":")
        if stripped in SECTION_HEADERS:
            current_section = stripped
            sections[current_section] = []
        else:
            sections[current_section].append(line)

    return {name: "\n".join(content).strip() for name, content in sections.items()}


def extract_entities(text: str) -> ExtractedEntities:
    """
    Extract structural entities from resume text using spaCy NER and regex.

    If no spaCy model is available, falls back gracefully to regex-only
    extraction (name and organizations will be empty; emails and phones
    are always extracted via regex regardless).

    Note: `skills` and `job_titles` are intentionally NOT populated here.
    Both require judgment (synonym handling, inferring skills from described
    work, distinguishing a skill from a similarly-named project) that a
    hardcoded vocabulary or NER label can't reliably provide. Those fields
    are filled in by the LLM step in core/analysis/llm_feedback.py and merged
    into this object afterward — see core/pipeline.py.
    """
    nlp = get_nlp()

    organizations: list[str] = []
    full_name: str | None = None

    if nlp is not None:
        doc = nlp(text)
        organizations = sorted({ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"})
        # PERSON entities: take the most frequently mentioned one as a best guess
        # for the candidate's name (resumes often repeat the name in headers/footers).
        person_mentions = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
        full_name = max(set(person_mentions), key=person_mentions.count) if person_mentions else None

    return ExtractedEntities(
        full_name=full_name,
        emails=extract_emails(text),
        phones=extract_phones(text),
        skills=[],       # filled in later from the LLM pass
        organizations=organizations,
        job_titles=[],   # filled in later from the LLM pass
    )
