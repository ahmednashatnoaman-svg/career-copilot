"""Application generation agent node for creating tailored CV, cover letter, and email."""

from app.agents.application.generators import (
    ApplicationPackage,
    application_email,
    cover_letter,
    tailor_cv,
)
from app.orchestrator.state import CopilotState


def application_node(state: CopilotState) -> dict:
    """Generate application materials: tailored CV, cover letter, and email.

    This node:
    1. Extracts resume text from `state["cv_analysis"]`
    2. Retrieves the top job from `state["market"]["jobs"]`
    3. Generates tailored CV, cover letter (≤400 words), and email
    4. Returns an ApplicationPackage with status="DRAFT" (NOT submitted)

    Args:
        state: The shared LangGraph state containing cv_analysis and market data.

    Returns:
        A dict with partial state update: {"application": ApplicationPackage}
    """
    cv_analysis = state.get("cv_analysis") or {}
    market = state.get("market") or {}
    jobs = market.get("jobs") or []

    # Handle empty inputs gracefully
    if not jobs or not cv_analysis:
        return {
            "application": ApplicationPackage(
                tailored_cv="",
                cover_letter="",
                email="",
                status="DRAFT",
            ).model_dump(mode="json")
        }

    # Extract resume text from cv_analysis
    resume_text = cv_analysis.get("resume_text", "")
    if not resume_text:
        # Fallback: build resume from analysis fields
        resume_parts = []
        if cv_analysis.get("summary"):
            resume_parts.append(cv_analysis["summary"])
        if cv_analysis.get("skills"):
            resume_parts.append(", ".join(cv_analysis["skills"]))
        if cv_analysis.get("job_titles"):
            resume_parts.append(", ".join(cv_analysis["job_titles"]))
        resume_text = " ".join(resume_parts) or "No resume data"

    # Use the first (highest-ranked) job
    job = jobs[0]
    company_name = job.company

    # Generate application materials
    tailored_cv_text = tailor_cv(resume_text, job)
    cover_letter_text = cover_letter(resume_text, job, company_name)
    email_text = application_email(resume_text, job)

    # Create ApplicationPackage with status="DRAFT"
    app_package = ApplicationPackage(
        tailored_cv=tailored_cv_text,
        cover_letter=cover_letter_text,
        email=email_text,
        status="DRAFT",
    )

    return {"application": app_package.model_dump(mode="json")}
