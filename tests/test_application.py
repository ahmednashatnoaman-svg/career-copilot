"""Tests for the application generation agent: CV tailoring, cover letter, email."""

import pytest

from app.agents.application.agent import application_node
from app.agents.application.generators import (
    ApplicationPackage,
    application_email,
    cover_letter,
    tailor_cv,
)
from app.orchestrator.state import CopilotState
from app.tools.jobsource.base import JobPosting


@pytest.fixture
def canned_resume():
    """Canned resume text for testing."""
    return """
    Jane Doe
    Senior Backend Engineer | Python | FastAPI | Kubernetes

    Experience:
    - 3 years as Backend Engineer at TechCorp
    - Built high-scale microservices with FastAPI and Kubernetes
    - Led team of 5 engineers on payment system redesign

    Skills: Python, FastAPI, LangGraph, Kubernetes, PostgreSQL, Docker
    Education: BS Computer Science, State University
    """


@pytest.fixture
def canned_job():
    """Canned job posting for testing."""
    return JobPosting(
        title="Senior Backend Engineer",
        company="NextGen AI Inc",
        location="San Francisco, CA",
        url="https://example.com/job",
        salary="$150k-180k",
        source="LinkedIn",
        snippet="Looking for experienced Backend Engineer with Python and LangGraph expertise",
    )


@pytest.fixture
def monkeypatch_llm(monkeypatch):
    """Monkeypatch get_llm to return a stub LLM."""

    class StubResponse:
        def __init__(self, content):
            self.content = content

    class StubLLM:
        def invoke(self, prompt):
            # Return different content based on prompt hints
            if "tailored" in prompt.lower() or "cv" in prompt.lower():
                return StubResponse(
                    "Jane Doe, Senior Backend Engineer. 3 years building scalable systems with Python, FastAPI, "
                    "Kubernetes. Led team of 5. Proven track record in microservices architecture and system design."
                )
            elif "cover letter" in prompt.lower():
                return StubResponse(
                    "I am excited to apply for the Senior Backend Engineer position at NextGen AI Inc. "
                    "With 3 years of backend engineering experience and expertise in FastAPI and Kubernetes, "
                    "I am confident I can contribute significantly to your team. I have a proven track record "
                    "of designing and implementing high-scale microservices. I am skilled in Python, FastAPI, "
                    "and cloud-native architecture. My recent work at TechCorp involved leading a team to redesign "
                    "our payment system, improving performance by 40%. I am eager to bring these skills to NextGen AI Inc "
                    "and am ready to tackle new challenges." * 3  # Make it long to test truncation
                )
            elif "email" in prompt.lower():
                return StubResponse(
                    "Hi Hiring Team,\n\nI am writing to express my interest in the Senior Backend Engineer role. "
                    "My background in FastAPI and Kubernetes aligns well with your requirements. "
                    "I look forward to discussing how I can contribute.\n\nBest regards,\nJane Doe"
                )
            return StubResponse("Generated content")

    def stub_get_llm(task="reason", temperature=0.0, max_tokens=None):
        return StubLLM()

    monkeypatch.setattr(
        "app.agents.application.generators.get_llm",
        stub_get_llm,
        raising=True,
    )


def test_tailor_cv_returns_non_empty(monkeypatch_llm, canned_resume, canned_job):
    """RED: tailor_cv returns non-empty string."""
    result = tailor_cv(canned_resume, canned_job)

    assert isinstance(result, str)
    assert len(result) > 0
    assert len(result.split()) > 0  # Has words


def test_cover_letter_returns_non_empty(monkeypatch_llm, canned_resume, canned_job):
    """RED: cover_letter returns non-empty string."""
    result = cover_letter(canned_resume, canned_job, "NextGen AI Inc")

    assert isinstance(result, str)
    assert len(result) > 0


def test_cover_letter_respects_400_word_cap(monkeypatch_llm, canned_resume, canned_job):
    """RED: cover_letter enforces ≤400-word cap (truncates if needed)."""
    result = cover_letter(canned_resume, canned_job, "NextGen AI Inc")

    word_count = len(result.split())
    assert word_count <= 400, f"Cover letter has {word_count} words, expected ≤ 400"


def test_application_email_returns_non_empty(monkeypatch_llm, canned_resume, canned_job):
    """RED: application_email returns non-empty string."""
    result = application_email(canned_resume, canned_job)

    assert isinstance(result, str)
    assert len(result) > 0


def test_application_node_returns_draft_package(monkeypatch_llm, canned_resume, canned_job):
    """RED: application_node returns ApplicationPackage with status='DRAFT'."""
    state = CopilotState(
        cv_analysis={"resume_text": canned_resume},
        market={"jobs": [canned_job]},
    )

    result = application_node(state)

    # Check structure
    assert "application" in result
    app_pkg = result["application"]

    # Check it's an ApplicationPackage
    assert isinstance(app_pkg, ApplicationPackage)

    # Check fields
    assert isinstance(app_pkg.tailored_cv, str)
    assert len(app_pkg.tailored_cv) > 0

    assert isinstance(app_pkg.cover_letter, str)
    assert len(app_pkg.cover_letter) > 0

    assert isinstance(app_pkg.email, str)
    assert len(app_pkg.email) > 0

    # Check status is DRAFT
    assert app_pkg.status == "DRAFT"


def test_application_package_status_default():
    """Test ApplicationPackage status defaults to 'DRAFT'."""
    pkg = ApplicationPackage(
        tailored_cv="CV content",
        cover_letter="Letter content",
        email="Email content",
    )

    assert pkg.status == "DRAFT"


def test_application_package_with_explicit_status():
    """Test ApplicationPackage can be instantiated with explicit status."""
    pkg = ApplicationPackage(
        tailored_cv="CV content",
        cover_letter="Letter content",
        email="Email content",
        status="DRAFT",
    )

    assert pkg.status == "DRAFT"
