from operator import add
from typing import Annotated, TypedDict

from app.agents.market_research.schemas import (
    JobPosting,
    LaneQuery,
    MarketAgentInput,
    MarketAgentOutput,
    MarketTrend,
    PlannerOutput,
    SalaryInsight,
    SkillGap,
)


class MarketAgentState(TypedDict):
    # Set once by whoever invokes the graph (e.g. the Supervisor).
    # Everything the planner and lane nodes need lives inside this object.
    input: MarketAgentInput

    # Written by planner_node.
    # Lane nodes read this to know what to search for.
    planner_output: PlannerOutput
    lane_queries: list[LaneQuery]

    # Written by each lane node in parallel.
    # Annotated[..., add] means parallel branches append, not overwrite.
    postings: Annotated[list[JobPosting], add]
    salaries: Annotated[list[SalaryInsight], add]
    trends:   Annotated[list[MarketTrend], add]

    # Written by skill_gap_node, accumulated across parallel branches.
    skill_gaps: Annotated[list[SkillGap], add]

    # Written by validator_node. Final output returned to the Supervisor.
    validated_output: MarketAgentOutput