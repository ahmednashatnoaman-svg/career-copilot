"""Job Matching agent node using semantic embedding-based ranking."""

from pydantic import BaseModel

from app.llm.provider import get_llm
from app.orchestrator.state import CopilotState
from app.rag.embeddings import embed_texts
from app.tools.jobsource.base import JobPosting


class RankedMatch(BaseModel):
    """A job posting with its semantic match score and rationale."""

    job: JobPosting
    score: float
    rationale: str


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python, no numpy).

    Args:
        vec_a: First vector (list of floats).
        vec_b: Second vector (list of floats).

    Returns:
        Cosine similarity in range [0.0, 1.0], or 0.0 if either vector is zero.
    """
    if len(vec_a) != len(vec_b):
        return 0.0

    # Compute dot product
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))

    # Compute magnitudes
    mag_a = sum(a * a for a in vec_a) ** 0.5
    mag_b = sum(b * b for b in vec_b) ** 0.5

    # Avoid division by zero
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot_product / (mag_a * mag_b)


def _generate_rationale(job: JobPosting, score: float) -> str:
    """Generate an LLM-powered rationale for why a job matches the candidate.

    Args:
        job: The job posting being evaluated.
        score: The computed semantic similarity score.

    Returns:
        A concise rationale string.
    """
    llm = get_llm(task="fast")
    prompt = f"""Given this job posting and a semantic match score, provide a brief 1-2 sentence rationale:

Job Title: {job.title}
Company: {job.company}
Snippet: {job.snippet or "N/A"}
Match Score: {score:.2%}

Rationale:"""

    response = llm.invoke(prompt)
    return response.content.strip()


def matching_node(state: CopilotState) -> dict:
    """Rank job postings by semantic similarity to the candidate's CV.

    This node:
    1. Extracts CV profile text from `state["cv_analysis"]`
    2. Embeds the CV profile and all jobs in `state["market"]["jobs"]`
    3. Scores each job by cosine similarity
    4. Optionally generates LLM rationales for top matches
    5. Returns ranked matches sorted by score (descending)

    Args:
        state: The shared LangGraph state containing cv_analysis and market data.

    Returns:
        A dict with partial state update: {"matching": {"ranked": list[RankedMatch]}}
    """
    cv_analysis = state.get("cv_analysis") or {}
    market = state.get("market") or {}
    jobs = market.get("jobs") or []

    # Handle empty inputs gracefully
    if not jobs or not cv_analysis:
        return {"matching": {"ranked": []}}

    # Build CV profile text from analysis
    cv_text_parts = []
    if cv_analysis.get("summary"):
        cv_text_parts.append(cv_analysis["summary"])
    if cv_analysis.get("skills"):
        cv_text_parts.append(", ".join(cv_analysis["skills"]))
    if cv_analysis.get("job_titles"):
        cv_text_parts.append(", ".join(cv_analysis["job_titles"]))
    if cv_analysis.get("strengths"):
        cv_text_parts.append(", ".join(cv_analysis["strengths"]))

    cv_text = " ".join(cv_text_parts) if cv_text_parts else "No CV data"

    # Prepare texts for embedding: CV first, then all jobs
    texts_to_embed = [cv_text] + [
        f"{job.title} {job.company} {job.snippet or ''}" for job in jobs
    ]

    # Embed all texts
    embeddings = embed_texts(texts_to_embed)
    cv_embedding = embeddings[0]
    job_embeddings = embeddings[1:]

    # Score each job by cosine similarity
    scored_jobs = []
    for job, job_emb in zip(jobs, job_embeddings, strict=False):
        score = _cosine_similarity(cv_embedding, job_emb)
        rationale = _generate_rationale(job, score)
        ranked_match = RankedMatch(job=job, score=score, rationale=rationale)
        scored_jobs.append(ranked_match)

    # Sort by score descending
    ranked_matches = sorted(scored_jobs, key=lambda m: m.score, reverse=True)

    return {"matching": {"ranked": ranked_matches}}
