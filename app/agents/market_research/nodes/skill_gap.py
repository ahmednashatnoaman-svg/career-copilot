"""
nodes/skill_gap.py — Skill Gap Analysis Node
============================================

WHAT THIS FILE DOES
-------------------
Compares the user's current skills against skills demanded in job postings
and market trends, identifying gaps rated by frequency and market.

HYBRID APPROACH
---------------
  Deterministic (counting + importance rating):
    - Extracts demanded skills from postings + trends
    - Counts frequency per market mode
    - Rates importance: high (≥3), medium (2), low (1)
    - This stays deterministic — same input always same gaps

  LLM (reason writing only):
    - Writes one meaningful sentence explaining WHY each gap matters
    - Uses job titles and sources actually seen in the data
    - Falls back to a clear generic reason if LLM fails

HOW IT WORKS
------------
1. Extract user skills from state["input"]
2. Count demanded skills from postings (title + description) and
   trends (related_skills) — grouped by market mode
3. Identify gaps: demanded skills the user doesn't have
4. Rate importance by frequency
5. LLM writes a human-readable reason per gap
6. Return {"skill_gaps": list[SkillGap]}

TEAMMATES
---------
- Skills dictionary lives in nodes/trends.py (KNOWN_SKILLS) — add there
- LLM model controlled by .env (LLM_PROVIDER / LLM_MODEL)
- Importance thresholds: edit _rate_importance() below
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from app.agents.market_research.llm import get_llm
from app.agents.market_research.nodes.trends import KNOWN_SKILLS
from app.agents.market_research.schemas import JobPosting, MarketMode, MarketTrend, SkillGap
from app.agents.market_research.state import MarketAgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill extraction — uses shared KNOWN_SKILLS from trends.py
# ---------------------------------------------------------------------------

def _extract_skills_from_text(text: str) -> list[str]:
    """
    Extract known skills from a block of text.
    Uses KNOWN_SKILLS imported from trends.py — one dictionary for the project.
    """
    text_lower = text.lower()
    found: set[str] = set()

    for pattern, display_name in KNOWN_SKILLS.items():
        escaped = re.escape(pattern)
        if any(c in pattern for c in ("+", "#", ".")):
            regex = escaped
        else:
            regex = r'\b' + escaped + r'\b'

        if re.search(regex, text_lower):
            found.add(display_name)

    return list(found)


# ---------------------------------------------------------------------------
# Market mode detection
# ---------------------------------------------------------------------------

def _determine_market(item: JobPosting | MarketTrend) -> MarketMode:
    """Map a posting or trend to its market mode based on source and location."""
    src = item.source.name.lower()

    if isinstance(item, JobPosting):
        loc = item.location.lower()
    else:
        loc = ""

    if src in ("wuzzuf", "bayt") or "egypt" in loc or "cairo" in loc:
        return "egypt"
    if src in ("upwork", "mostaql", "khamsat"):
        return "freelance"
    return "international"


# ---------------------------------------------------------------------------
# Importance rating
# ---------------------------------------------------------------------------

def _rate_importance(count: int) -> Literal["low", "medium", "high"]:
    """
    Rate skill importance by demand frequency.
    Thresholds are here — easy to adjust without touching other logic.
    """
    if count >= 3:
        return "high"
    if count == 2:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# LLM reason writing
# ---------------------------------------------------------------------------

_REASON_PROMPT = """
You are a career advisor writing concise skill gap explanations.

Write ONE sentence explaining why the user should learn "{skill}" 
based on the market data below. Be specific — mention role titles,
locations, or sources from the data. Do not be generic.

Market: {market}
Demand count: {count} job listing(s) / trend(s)
Sample job titles where this skill appears: {sample_titles}

Rules:
- One sentence only, max 30 words
- Mention the market (e.g. "Cairo", "freelance platforms", "international roles")
- Do not start with "I" or "You should"
- Example good reason: "PyTorch appears in 4 Cairo AI Engineer postings on Wuzzuf, making it essential for local ML roles"
- Example bad reason: "This skill is required in the market"
"""


def _write_reason(
    skill: str,
    market: MarketMode,
    count: int,
    sample_titles: list[str],
) -> str:
    """
    Ask LLM to write a meaningful reason for the skill gap.
    Falls back to a clear generic reason if LLM fails.
    """
    # Fallback — used if LLM fails or returns empty
    market_label = {
        "egypt":         "the Egyptian job market",
        "freelance":     "freelance platforms",
        "international": "international roles",
    }.get(market, market)

    fallback = (
        f"Appears in {count} listing(s) or trend(s) in {market_label}, "
        f"suggesting growing demand for this skill."
    )

    try:
        llm   = get_llm("fast")
        prompt = _REASON_PROMPT.format(
            skill         = skill,
            market        = market,
            count         = count,
            sample_titles = ", ".join(sample_titles[:5]) or "N/A",
        )
        response = llm.invoke(prompt)
        reason   = response.content.strip()

        # Sanity check — LLM sometimes returns empty or too long
        if not reason or len(reason) > 300:
            return fallback

        return reason

    except Exception as e:
        logger.warning(f"[skill_gap] LLM reason writing failed for '{skill}': {e}")
        return fallback


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def skill_gap_node(state: MarketAgentState) -> dict:
    """
    LangGraph node — performs skill gap analysis.

    Reads  : state["postings"], state["trends"], state["input"]
    Writes : state["skill_gaps"] (appended via reducer — see state.py)
    """
    # --- 1. User's current skills (lowercased for comparison) ---
    user_input  = state.get("input")
    user_skills: set[str] = set()
    if user_input and hasattr(user_input, "skills"):
        user_skills = {s.strip().lower() for s in user_input.skills if s.strip()}

    postings: list[JobPosting]   = state.get("postings", [])
    trends:   list[MarketTrend]  = state.get("trends",   [])

    # --- 2. Count demanded skills per market ---
    # Structure: {market_mode: {skill_display_name: count}}
    demand: dict[MarketMode, dict[str, int]] = {
        "egypt":         {},
        "freelance":     {},
        "international": {},
    }

    # Collect sample job titles per skill for LLM context
    # Structure: {market_mode: {skill: [title1, title2, ...]}}
    sample_titles: dict[MarketMode, dict[str, list[str]]] = {
        "egypt":         {},
        "freelance":     {},
        "international": {},
    }

    # Count from postings (title + description)
    for post in postings:
        market = _determine_market(post)
        text   = f"{post.title} {post.description or ''}".strip()
        skills = _extract_skills_from_text(text)

        for skill in skills:
            demand[market][skill] = demand[market].get(skill, 0) + 1
            sample_titles[market].setdefault(skill, [])
            if post.title and post.title not in sample_titles[market][skill]:
                sample_titles[market][skill].append(post.title)

    # Count from trends (related_skills already extracted)
    for trend in trends:
        market = _determine_market(trend)
        for skill in trend.related_skills:
            demand[market][skill] = demand[market].get(skill, 0) + 1
            # Trends don't have titles — use insight as context
            sample_titles[market].setdefault(skill, [])
            if trend.insight and trend.insight not in sample_titles[market][skill]:
                sample_titles[market][skill].append(trend.insight[:80])

    # --- 3. Identify gaps + rate importance ---
    skill_gaps: list[SkillGap] = []

    for market, demanded in demand.items():
        for skill, count in demanded.items():
            # Skip skills the user already has
            if skill.lower() in user_skills:
                continue

            importance = _rate_importance(count)
            titles     = sample_titles[market].get(skill, [])
            reason     = _write_reason(skill, market, count, titles)

            skill_gaps.append(
                SkillGap(
                    skill      = skill,
                    importance = importance,
                    reason     = reason,
                    market     = market,
                )
            )

    # Sort: high → medium → low, then alphabetically within each group
    order = {"high": 0, "medium": 1, "low": 2}
    skill_gaps.sort(key=lambda g: (order[g.importance], g.skill))

    logger.info(f"[skill_gap] identified {len(skill_gaps)} skill gaps")
    return {"skill_gaps": skill_gaps}