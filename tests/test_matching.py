"""Tests for the job matching agent node with semantic ranking."""

import pytest

from app.agents.matching.agent import RankedMatch, matching_node
from app.orchestrator.state import CopilotState
from app.tools.jobsource.base import JobPosting


@pytest.fixture
def canned_cv_profile():
    """Canned CV analysis for testing."""
    return {
        "entities": "Jane Doe",
        "summary": "3 years Python backend engineer, FastAPI, LangGraph, Kubernetes",
        "skills": ["Python", "FastAPI", "LangGraph", "Kubernetes", "PostgreSQL"],
        "job_titles": ["Backend Engineer", "Senior Backend Developer"],
        "strengths": ["System design", "Problem solving", "Team leadership"],
        "weaknesses": ["Machine learning", "Mobile development"],
    }


@pytest.fixture
def canned_jobs():
    """Canned job postings for testing."""
    return [
        JobPosting(
            title="Senior Backend Engineer",
            company="TechCorp",
            location="San Francisco, CA",
            url="https://example.com/job1",
            salary="$150k-180k",
            source="LinkedIn",
            snippet="Looking for Senior Backend Engineer with Python and FastAPI experience",
        ),
        JobPosting(
            title="Data Scientist",
            company="DataInc",
            location="New York, NY",
            url="https://example.com/job2",
            salary="$140k-160k",
            source="LinkedIn",
            snippet="Data science role focusing on machine learning and analytics",
        ),
        JobPosting(
            title="Frontend Engineer",
            company="WebDev Inc",
            location="Los Angeles, CA",
            url="https://example.com/job3",
            salary="$120k-140k",
            source="Indeed",
            snippet="Build responsive web interfaces using React and TypeScript",
        ),
    ]


@pytest.fixture
def monkeypatch_embeddings(monkeypatch):
    """Monkeypatch embed_texts to return deterministic vectors.

    Returns vectors such that:
    - CV profile vector: [1.0, 0.0, 0.0, 0.0]
    - Job 1 (Senior Backend): [0.9, 0.1, 0.0, 0.0]  -> cosine ≈ 0.99
    - Job 2 (Data Scientist): [0.0, 1.0, 0.0, 0.0]  -> cosine ≈ 0.0
    - Job 3 (Frontend): [0.0, 0.0, 1.0, 0.0]        -> cosine ≈ 0.0
    """
    def stubbed_embed_texts(texts):
        vectors = []
        for text in texts:
            if "Jane" in text or "Jane Doe" in text or "Backend" in text:
                # CV or Job 1 (both backend-focused)
                vectors.append([0.9, 0.1, 0.0, 0.0])
            elif "Data" in text or "machine learning" in text or "analytics" in text:
                # Job 2 (data science)
                vectors.append([0.0, 1.0, 0.0, 0.0])
            elif "Frontend" in text or "React" in text or "TypeScript" in text:
                # Job 3 (frontend)
                vectors.append([0.0, 0.0, 1.0, 0.0])
            else:
                # Default: generic vector
                vectors.append([0.5, 0.5, 0.0, 0.0])
        return vectors

    monkeypatch.setattr(
        "app.agents.matching.agent.embed_texts",
        stubbed_embed_texts,
        raising=True,
    )


@pytest.fixture
def monkeypatch_llm(monkeypatch):
    """Monkeypatch get_llm to return a stub LLM for generating rationales."""
    stub_llm = type("StubLLM", (), {
        "invoke": lambda self, msg: type("Response", (), {
            "content": "Strong match: candidate has 3 years backend experience and FastAPI expertise."
        })()
    })()

    monkeypatch.setattr(
        "app.agents.matching.agent.get_llm",
        lambda task=None: stub_llm,
        raising=True,
    )


def test_matching_node_returns_ranked_matches(monkeypatch_embeddings, monkeypatch_llm, canned_cv_profile, canned_jobs):
    """RED: matching_node embeds and scores jobs, returns ranked matches with rationale."""
    state = CopilotState(
        cv_analysis=canned_cv_profile,
        market={"jobs": canned_jobs},
    )

    result = matching_node(state)

    # Check structure
    assert "matching" in result
    assert "ranked" in result["matching"]

    ranked = result["matching"]["ranked"]
    assert isinstance(ranked, list)
    assert len(ranked) == 3

    # Each item is a RankedMatch
    for item in ranked:
        assert isinstance(item, RankedMatch)
        assert isinstance(item.job, JobPosting)
        assert isinstance(item.score, float)
        assert isinstance(item.rationale, str)
        assert 0.0 <= item.score <= 1.0
        assert len(item.rationale) > 0

    # Check ordering: sorted by score descending
    scores = [item.score for item in ranked]
    assert scores == sorted(scores, reverse=True)


def test_matching_node_empty_jobs(monkeypatch_embeddings, monkeypatch_llm, canned_cv_profile):
    """Test matching_node with empty job list."""
    state = CopilotState(
        cv_analysis=canned_cv_profile,
        market={"jobs": []},
    )

    result = matching_node(state)

    assert "matching" in result
    assert "ranked" in result["matching"]
    assert result["matching"]["ranked"] == []


def test_matching_node_no_cv_analysis(monkeypatch_embeddings, monkeypatch_llm, canned_jobs):
    """Test matching_node with missing CV analysis."""
    state = CopilotState(
        cv_analysis={},
        market={"jobs": canned_jobs},
    )

    result = matching_node(state)

    assert "matching" in result
    assert "ranked" in result["matching"]
    # With empty CV, should still handle gracefully
    assert isinstance(result["matching"]["ranked"], list)


def test_ranked_match_has_required_fields():
    """Test RankedMatch model has required fields."""
    job = JobPosting(
        title="Test Job",
        company="Test Corp",
        location="NYC",
        url="https://example.com",
        source="test",
    )

    match = RankedMatch(
        job=job,
        score=0.85,
        rationale="Strong technical fit",
    )

    assert match.job.title == "Test Job"
    assert match.score == 0.85
    assert match.rationale == "Strong technical fit"
