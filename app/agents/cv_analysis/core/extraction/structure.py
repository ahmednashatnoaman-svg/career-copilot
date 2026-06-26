"""
Extracts deterministic structural info from resume text: contact info via
regex and section headers via string matching.

Note: full_name, organizations, skills, and job_titles are NOT extracted
here. General-purpose NER (spaCy) performed poorly on resume text in
practice — out-of-distribution formatting (fragments, headers, no sentence
context) that statistical NER wasn't trained for. All four now come from
the LLM step in analysis/llm_feedback.py, which has actual resume context
to reason with. See pipeline.py for how they're merged in.
"""

import re

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
    "internships",
    "trainings",
    "internships & trainings"
]

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
