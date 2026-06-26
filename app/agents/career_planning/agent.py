"""Career planning agent node using LLM synthesis of cv_analysis, market, portfolio."""

from pydantic import BaseModel

from app.llm.provider import get_llm
from app.orchestrator.state import CopilotState


class Milestone(BaseModel):
    """Individual career milestone with title, timeframe, and detail."""

    title: str
    timeframe: str
    detail: str


class CareerPlan(BaseModel):
    """Career plan synthesized from cv_analysis, market skill_gaps, and portfolio."""

    target_role: str
    roadmap: list[Milestone]
    certifications: list[str]
    milestones: list[str]


def career_planning_node(state: CopilotState) -> dict[str, CareerPlan]:
    """Synthesize career plan from upstream agents' analysis.

    Reads cv_analysis, market.skill_gaps, and portfolio from state.
    Uses LLM with structured output to generate a grounded CareerPlan.

    Args:
        state: LangGraph state with cv_analysis, market, portfolio keys.

    Returns:
        Dict with key "career_plan" containing a structured CareerPlan.
    """
    # Extract upstream state
    cv_analysis = state.get("cv_analysis", {})
    market = state.get("market", {})
    portfolio = state.get("portfolio", {})

    # Build synthesis prompt
    cv_summary = cv_analysis.get("summary", "Unknown background")
    skills = cv_analysis.get("skills", [])
    skill_gaps = market.get("skill_gaps", [])
    emerging_roles = market.get("emerging_roles", [])
    top_projects = portfolio.get("top_projects", [])

    skills_str = ", ".join(skills) if skills else "None identified"
    gaps_str = ", ".join(skill_gaps) if skill_gaps else "None identified"
    roles_str = ", ".join(emerging_roles) if emerging_roles else "Unknown"
    projects_str = ", ".join([p.get("name", "Unknown") for p in top_projects]) if top_projects else "None"

    prompt = f"""Based on the following career context, synthesize a comprehensive career plan:

CV Summary: {cv_summary}
Current Skills: {skills_str}
Skill Gaps: {gaps_str}
Emerging Roles in Market: {roles_str}
Portfolio Projects: {projects_str}

Generate a career plan that:
1. Selects a realistic target role from emerging roles (or synthesize a hybrid if appropriate)
2. Provides 3-4 concrete roadmap milestones (each with title, timeframe, detail)
3. Recommends 2-3 relevant certifications
4. Lists 3-4 actionable milestones to demonstrate progress

Ground all recommendations in the person's current skills and market demand."""

    # Use LLM with structured output
    llm = get_llm(task="reason")
    structured_llm = llm.with_structured_output(CareerPlan)
    career_plan = structured_llm.invoke(prompt)

    return {"career_plan": career_plan}
