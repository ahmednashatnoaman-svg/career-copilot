"""Generators for tailored CV, cover letter, and application email."""

from pydantic import BaseModel

from app.llm.provider import get_llm
from app.tools.jobsource.base import JobPosting


class ApplicationPackage(BaseModel):
    """Generated application materials: tailored CV, cover letter, email."""

    tailored_cv: str
    cover_letter: str
    email: str
    status: str = "DRAFT"


def tailor_cv(resume: str, job: JobPosting) -> str:
    """Generate a tailored CV for a specific job posting.

    Args:
        resume: The candidate's resume text.
        job: The target job posting.

    Returns:
        Tailored CV as a string.
    """
    llm = get_llm(task="reason")
    prompt = f"""Tailor the following resume to match the job posting. Highlight relevant experience and skills.

Resume:
{resume}

Job Title: {job.title}
Company: {job.company}
Job Snippet: {job.snippet or "N/A"}

Provide a tailored CV summary (2-3 sentences) that highlights the strongest fit:"""

    response = llm.invoke(prompt)
    return response.content.strip()


def cover_letter(resume: str, job: JobPosting, company: str) -> str:
    """Generate a cover letter for a job application (≤400 words).

    Args:
        resume: The candidate's resume text.
        job: The target job posting.
        company: The company name.

    Returns:
        Cover letter as a string, guaranteed ≤400 words.
    """
    llm = get_llm(task="reason")
    prompt = f"""Write a professional cover letter for this job application. Keep it under 400 words.

Resume:
{resume}

Job Title: {job.title}
Company: {company}
Job Description: {job.snippet or "N/A"}

Cover Letter (max 400 words):"""

    response = llm.invoke(prompt)
    content = response.content.strip()

    # Enforce ≤400-word cap by truncating if necessary
    words = content.split()
    if len(words) > 400:
        content = " ".join(words[:400])

    return content


def application_email(resume: str, job: JobPosting) -> str:
    """Generate a professional email to accompany the application.

    Args:
        resume: The candidate's resume text.
        job: The target job posting.

    Returns:
        Application email as a string.
    """
    llm = get_llm(task="fast")
    prompt = f"""Write a professional email to accompany a job application. Keep it concise (under 200 words).

Resume:
{resume}

Job Title: {job.title}
Company: {job.company}

Email:"""

    response = llm.invoke(prompt)
    return response.content.strip()
