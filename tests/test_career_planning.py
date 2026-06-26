"""Unit tests for career planning agent node."""

from unittest.mock import MagicMock, patch

from app.agents.career_planning.agent import (
    CareerPlan,
    Milestone,
    career_planning_node,
)
from app.orchestrator.state import CopilotState

# --- Canned Upstream State ---
CANNED_CV_ANALYSIS = {
    "summary": "Senior backend engineer with 8 years experience",
    "skills": ["Python", "Go", "PostgreSQL", "Kubernetes"],
    "experience": [
        {"role": "Senior Engineer", "company": "TechCorp", "years": 3},
    ],
}

CANNED_MARKET = {
    "skill_gaps": ["Rust", "ML basics", "System design at scale"],
    "emerging_roles": ["ML Engineer", "Platform Engineer", "Staff Engineer"],
    "demand_trend": "high",
}

CANNED_PORTFOLIO = {
    "top_projects": [
        {"name": "distributed-cache", "stars": 250, "language": "Go"},
    ],
    "languages": {"Go": 15, "Python": 20},
}


def test_career_planning_node_success():
    """Test career_planning_node returns CareerPlan with >=1 roadmap milestone."""
    state: CopilotState = {
        "user_id": "user123",
        "cv_analysis": CANNED_CV_ANALYSIS,
        "market": CANNED_MARKET,
        "portfolio": CANNED_PORTFOLIO,
    }

    # Stub the structured LLM
    canned_career_plan = CareerPlan(
        target_role="Staff Engineer (ML-Systems Hybrid)",
        roadmap=[
            Milestone(
                title="Master Rust & Systems Programming",
                timeframe="3-4 months",
                detail="Complete Rust book, build 2 systems projects",
            ),
            Milestone(
                title="Learn ML Fundamentals",
                timeframe="4-5 months",
                detail="Take ML course, implement neural nets from scratch",
            ),
            Milestone(
                title="Staff-level System Design",
                timeframe="2-3 months",
                detail="Study distributed systems, lead 1 arch doc",
            ),
        ],
        certifications=["AWS Solutions Architect", "CKAD"],
        milestones=[
            "Build Rust web service in production",
            "Lead cross-team ML pilot",
            "Publish system design blog post",
        ],
    )

    with patch("app.agents.career_planning.agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Stub structured output
        mock_structured_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_structured_llm.invoke.return_value = canned_career_plan

        # Call career_planning_node
        result = career_planning_node(state)

        # Assertions
        assert "career_plan" in result
        plan: CareerPlan = result["career_plan"]
        assert plan.target_role == "Staff Engineer (ML-Systems Hybrid)"
        assert len(plan.roadmap) >= 1
        assert all(isinstance(m, Milestone) for m in plan.roadmap)
        assert plan.roadmap[0].title == "Master Rust & Systems Programming"
        assert len(plan.certifications) > 0
        assert len(plan.milestones) > 0


def test_career_planning_node_minimal_state():
    """Test career_planning_node handles minimal/missing upstream state gracefully."""
    # Minimal state with only user_id
    state: CopilotState = {
        "user_id": "user456",
        # cv_analysis, market, portfolio are missing
    }

    with patch("app.agents.career_planning.agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Stub structured output to return a fallback CareerPlan
        mock_structured_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm
        fallback_plan = CareerPlan(
            target_role="Generalist Software Engineer",
            roadmap=[
                Milestone(
                    title="Explore",
                    timeframe="Open-ended",
                    detail="Build foundation skills",
                )
            ],
            certifications=[],
            milestones=[],
        )
        mock_structured_llm.invoke.return_value = fallback_plan

        # Call career_planning_node — should not crash
        result = career_planning_node(state)

        # Assertions: should return a valid CareerPlan
        assert "career_plan" in result
        plan: CareerPlan = result["career_plan"]
        assert plan is not None
        assert isinstance(plan, CareerPlan)
        assert plan.target_role is not None


def test_milestone_schema():
    """Test Milestone Pydantic schema validates correctly."""
    milestone = Milestone(
        title="Learn Rust",
        timeframe="6 months",
        detail="Complete The Rust Book and build a CLI tool",
    )
    assert milestone.title == "Learn Rust"
    assert milestone.timeframe == "6 months"
    assert milestone.detail is not None


def test_career_plan_schema():
    """Test CareerPlan Pydantic schema validates correctly."""
    plan = CareerPlan(
        target_role="Senior Backend Engineer",
        roadmap=[
            Milestone(
                title="Step 1",
                timeframe="3 months",
                detail="Learn new tech",
            )
        ],
        certifications=["AWS Solutions Architect"],
        milestones=["Deploy to production"],
    )
    assert plan.target_role == "Senior Backend Engineer"
    assert len(plan.roadmap) == 1
    assert len(plan.certifications) == 1
    assert len(plan.milestones) == 1
