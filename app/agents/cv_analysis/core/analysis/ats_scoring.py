"""
Deterministic ATS (Applicant Tracking System) friendliness scoring.

Deliberately rule-based, not LLM-judged: ATS parsability is about concrete,
checkable facts (does it have an email, is the structure parseable, are
standard section headers present) — not subjective quality. This keeps the
score explainable and consistent across runs.
"""

from app.agents.cv_analysis.core.extraction.structure import SECTION_HEADERS
from app.agents.cv_analysis.schemas import ATSCheck

MAX_SCORE = 100

# Each check is (points, description). Total of all points == MAX_SCORE.
CHECKS = {
    "has_email": 15,
    "has_phone": 10,
    "has_standard_sections": 25,
    "reasonable_length": 20,
    "no_excessive_special_chars": 15,
    "has_skills_section": 15,
}


def score_ats(
    *,
    cleaned_text: str,
    has_email: bool,
    has_phone: bool,
    detected_sections: dict[str, str],
) -> ATSCheck:
    issues: list[str] = []
    passed_checks: list[str] = []
    earned = 0

    # Contact info
    if has_email:
        earned += CHECKS["has_email"]
        passed_checks.append("Email address found")
    else:
        issues.append("No email address detected — ATS systems and recruiters need this to contact you")

    if has_phone:
        earned += CHECKS["has_phone"]
        passed_checks.append("Phone number found")
    else:
        issues.append("No phone number detected")

    # Standard section headers present (excluding the catch-all "header" bucket)
    found_sections = {name for name in detected_sections if name != "header" and detected_sections[name]}
    recognized = found_sections.intersection(SECTION_HEADERS)
    if len(recognized) >= 3:
        earned += CHECKS["has_standard_sections"]
        passed_checks.append(f"Standard section headers detected ({len(recognized)} found)")
    else:
        issues.append(
            "Fewer than 3 standard section headers detected (e.g. Experience, Education, "
            "Skills) — ATS parsers rely on these to categorize your content"
        )

    # Skills section specifically
    if any(name in found_sections for name in ("skills", "technical skills")):
        earned += CHECKS["has_skills_section"]
        passed_checks.append("Dedicated skills section found")
    else:
        issues.append("No dedicated 'Skills' section found — consider adding one for ATS keyword matching")

    # Length check — too short suggests missing content, too long suggests bloat
    word_count = len(cleaned_text.split())
    if 250 <= word_count <= 1200:
        earned += CHECKS["reasonable_length"]
        passed_checks.append(f"Resume length is reasonable ({word_count} words)")
    elif word_count < 250:
        issues.append(f"Resume seems short ({word_count} words) — may be missing detail")
    else:
        issues.append(f"Resume seems long ({word_count} words) — consider tightening for readability")

    # Special character density — high density often means tables/columns/icons
    # that break ATS text extraction
    special_chars = sum(1 for c in cleaned_text if not c.isalnum() and not c.isspace())
    special_ratio = special_chars / max(len(cleaned_text), 1)
    if special_ratio < 0.08:
        earned += CHECKS["no_excessive_special_chars"]
        passed_checks.append("Low special-character density (good — suggests simple, parseable formatting)")
    else:
        issues.append(
            "High density of special characters or symbols detected — may indicate tables, "
            "columns, or icons that some ATS parsers can't read correctly"
        )

    return ATSCheck(
        score=round((earned / MAX_SCORE) * 100),
        issues=issues,
        passed_checks=passed_checks,
    )
