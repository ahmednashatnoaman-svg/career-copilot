"""
planner.py — Market Agent Planner Node
=======================================

WHAT THIS FILE DOES
-------------------
Converts state["input"] (a MarketAgentInput) into:
  - state["planner_output"]  (PlannerOutput)
  - state["lane_queries"]    (list[LaneQuery])

It does NOT:
  - Call the web / any external API
  - Touch the cache or vector DB
  - Call an LLM
  - Generate recommendations or summaries

It's pure Python: same input → always same output, zero randomness.

HOW IT FITS IN THE GRAPH
-------------------------
  START → planner_node → postings_node ┐
                       → salaries_node ├→ skill_gap_node → validator_node → END
                       → trends_node   ┘

Routing is static (graph.py uses add_edge, not Send).
lane_queries carries search parameters for the lane nodes to read —
it does not drive routing.

TEAMMATES: only touch this file if planner logic changes.
State schema → state.py. Graph wiring → graph.py.
"""

from __future__ import annotations

from app.agents.market_research.schemas import (
    LaneQuery,
    LaneType,
    MarketMode,
    PlannerOutput,
    WorkPreferences,
)
from app.agents.market_research.state import MarketAgentState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def determine_market_modes(work_prefs: WorkPreferences) -> list[MarketMode]:
    """
    Return ordered market modes to activate: egypt → freelance → international.

    egypt        : work_location_preference is "local" or "both"
    freelance    : work_preferences.freelance is True
    international: work_location_preference is "abroad" or "both"
    """
    modes: list[MarketMode] = []

    if work_prefs.work_location_preference in ("local", "both"):
        modes.append("egypt")

    if work_prefs.freelance:
        modes.append("freelance")

    if work_prefs.work_location_preference in ("abroad", "both"):
        modes.append("international")

    return modes


def normalize_list(values: list[str], fallback: list[str] | None = None) -> list[str]:
    """
    Deduplicate + trim a list of strings, preserving first-seen order.

    >>> normalize_list([" MLOps Engineer ", "MLOps Engineer"])
    ['MLOps Engineer']
    >>> normalize_list([], fallback=["Egypt"])
    ['Egypt']
    """
    seen: set[str] = set()
    result: list[str] = []

    for item in values:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)

    return result if result else (fallback or [])


def build_lane_queries(
    market_modes: list[MarketMode],
    role_queries: list[str],
    locations: list[str],
) -> list[LaneQuery]:
    """
    Expand (market_modes × lanes × roles) into a flat list of LaneQuery objects.

    Lane nodes read this list to know what to search for.
    Routing itself is static (see graph.py) — this list carries parameters only.

    egypt mode   → uses first preferred location as search context
    freelance    → no location (platforms are global)
    international→ no location (platforms are global)
    """
    lanes: list[LaneType] = ["postings", "trends", "salary"]

    location_by_mode: dict[MarketMode, str | None] = {
        "egypt": locations[0] if locations else "Egypt",
        "freelance": None,
        "international": None,
    }

    queries: list[LaneQuery] = []

    for mode in market_modes:
        for lane in lanes:
            for role in role_queries:
                queries.append(
                    LaneQuery(
                        lane=lane,
                        market_mode=mode,
                        role=role,
                        location=location_by_mode[mode],
                    )
                )

    return queries


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def planner_node(state: MarketAgentState) -> dict:
    """
    LangGraph node — reads state["input"], writes planner_output + lane_queries.

    Returns a dict; LangGraph merges it into shared state.
    No I/O, no side effects.
    """
    agent_input = state["input"]

    # 1. Determine markets
    market_modes = determine_market_modes(agent_input.work_preferences)
    if not market_modes:
        market_modes = ["egypt"]  # safe fallback — never fan out to nothing

    # 2. Normalize
    role_queries = normalize_list(agent_input.target_roles,     fallback=["Software Engineer"])
    locations    = normalize_list(agent_input.preferred_locations, fallback=["Egypt"])
    skills       = normalize_list(agent_input.skills)

    # 3. Build lane queries (search params for lane nodes)
    lane_queries = build_lane_queries(market_modes, role_queries, locations)

    return {
        "planner_output": PlannerOutput(
            market_modes=market_modes,
            role_queries=role_queries,
            locations=locations,
            skills=skills,
        ),
        "lane_queries": lane_queries,
    }