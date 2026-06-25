"""CV API router — tailor CVs and generate cover letters."""

from __future__ import annotations

from fastapi import APIRouter, Body

router = APIRouter(prefix="/cv", tags=["cv"])


@router.post("/tailor")
async def tailor_cv(
    user_id: str = Body(...),
    resume_text: str = Body(...),
    job_description: str = Body(...),
    job_title: str = Body(""),
    company: str = Body(""),
):
    """Tailor a CV to a specific job description using ATS optimisation.

    Body:
        user_id:         The user's ID.
        resume_text:     Full text of the existing CV.
        job_description: Target job description.
        job_title:       Optional job title for context.
        company:         Optional company name for context.

    Returns:
        JSON with ``tailored_cv``, ``original_cv``, ``match_score``,
        ``job_title``, and ``company``.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        from app.llm.provider import get_llm  # noqa: PLC0415

        llm = get_llm("reason")

        tailor_prompt = (
            f"You are an expert ATS-optimized CV writer.\n\n"
            f"ORIGINAL CV:\n{resume_text}\n\n"
            f"TARGET JOB:\n"
            f"Title: {job_title} at {company}\n"
            f"Description: {job_description}\n\n"
            "Rewrite the CV to:\n"
            "1. Mirror keywords from the job description naturally\n"
            "2. Quantify achievements where possible\n"
            "3. Reorder sections to highlight most relevant experience first\n"
            "4. Keep length the same (no adding fake experience)\n"
            "5. Make it ATS-friendly\n\n"
            "Return ONLY the rewritten CV text, no commentary."
        )

        response = await llm.ainvoke(
            [
                SystemMessage(
                    content="You are an expert CV writer specialising in ATS optimisation."
                ),
                HumanMessage(content=tailor_prompt),
            ]
        )
        tailored_cv = response.content

        score_prompt = (
            "Rate how well this CV matches the job description on a scale of 0-100. "
            "Return ONLY the number.\n"
            f"CV:\n{resume_text}\n\nJOB:\n{job_description}"
        )
        score_response = await llm.ainvoke([HumanMessage(content=score_prompt)])
        try:
            score = int(score_response.content.strip().replace("%", ""))
        except (ValueError, AttributeError):
            score = 75

        return {
            "tailored_cv": tailored_cv,
            "original_cv": resume_text,
            "match_score": score,
            "job_title": job_title,
            "company": company,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "error": str(exc),
            "tailored_cv": resume_text,
            "original_cv": resume_text,
            "match_score": 0,
            "job_title": job_title,
            "company": company,
        }


@router.post("/cover-letter")
async def generate_cover_letter(
    user_id: str = Body(...),
    resume_text: str = Body(...),
    job_description: str = Body(...),
    job_title: str = Body(""),
    company: str = Body(""),
):
    """Generate a personalised cover letter from a CV and job description.

    Body:
        user_id:         The user's ID.
        resume_text:     Full text of the existing CV.
        job_description: Target job description.
        job_title:       Optional job title for context.
        company:         Optional company name for context.

    Returns:
        JSON with ``cover_letter``, ``job_title``, and ``company``.
    """
    try:
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        from app.llm.provider import get_llm  # noqa: PLC0415

        llm = get_llm("reason")

        prompt = (
            "Write a compelling, personalised cover letter (under 400 words).\n\n"
            f"CV SUMMARY:\n{resume_text[:2000]}\n\n"
            f"JOB:\nTitle: {job_title} at {company}\n{job_description[:1500]}\n\n"
            "Requirements:\n"
            '- Start with a strong hook (not "I am applying for...")\n'
            "- Highlight 2-3 specific achievements that match the job\n"
            "- Show company research/enthusiasm\n"
            "- End with a clear call to action\n"
            "- Professional but warm tone"
        )

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return {
            "cover_letter": response.content,
            "job_title": job_title,
            "company": company,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "cover_letter": "", "job_title": job_title, "company": company}
