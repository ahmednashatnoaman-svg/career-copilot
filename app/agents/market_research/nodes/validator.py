"""
nodes/validator.py — Market Agent Validator Node
===============================================

WHAT THIS FILE DOES
-------------------
Final gate before results reach the user. Validates, deduplicates,
filters by confidence, and compiles everything into a MarketAgentOutput.

FLOW
----
    1. Filter out items without valid sources
    2. Filter out low-confidence items (< MIN_CONFIDENCE)
    3. Deduplicate per type using meaningful keys (not string repr)
    4. Reconstruct Pydantic models safely (HttpUrl-aware)
    5. Return {"validated_output": MarketAgentOutput}

WHY model_dump(mode="json")
----------------------------
Source.url is a Pydantic HttpUrl field. model_dump() returns a Url
object — passing that back into JobPosting(**dict) fails. mode="json"
serializes HttpUrl to a plain string, making the round-trip safe.

TEAMMATES
---------
- Confidence threshold: edit MIN_CONFIDENCE below
- Dedup keys: edit _dedup_*() functions below
- Source validation logic: services/source_validation.py
"""

from __future__ import annotations

import logging

from app.agents.market_research.schemas import (
    JobPosting,
    MarketAgentOutput,
    MarketTrend,
    SalaryInsight,
    SkillGap,
)
from app.agents.market_research.services.source_validation import has_valid_source
from app.agents.market_research.state import MarketAgentState

logger = logging.getLogger(__name__)

# Items with confidence below this are dropped before final output
MIN_CONFIDENCE = 0.4


# ---------------------------------------------------------------------------
# Deduplication — meaningful keys per type, not string repr
# ---------------------------------------------------------------------------

def _dedup_postings(items: list[dict]) -> list[dict]:
    """
    Deduplicate job postings by source URL.
    Same URL = same posting regardless of title casing or timestamp.
    """
    seen:   set[str]  = set()
    result: list[dict] = []

    for item in items:
        url = str(item.get("source", {}).get("url", "")).strip()
        if url and url not in seen:
            seen.add(url)
            result.append(item)

    return result


def _dedup_salaries(items: list[dict]) -> list[dict]:
    """
    Deduplicate salary insights by (role, location, source name).
    Different sources for the same role+location are kept — they may
    show different ranges and are all useful.
    """
    seen:   set[tuple] = set()
    result: list[dict] = []

    for item in items:
        key = (
            item.get("role",     "").lower().strip(),
            item.get("location", "").lower().strip(),
            item.get("source",   {}).get("name", "").lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def _dedup_trends(items: list[dict]) -> list[dict]:
    """
    Deduplicate trends by source URL — same article = same trend.
    """
    seen:   set[str]  = set()
    result: list[dict] = []

    for item in items:
        url = str(item.get("source", {}).get("url", "")).strip()
        if url and url not in seen:
            seen.add(url)
            result.append(item)

    return result


def _dedup_gaps(items: list[dict]) -> list[dict]:
    """
    Deduplicate skill gaps by (skill, market) — same skill in same
    market from different sources should only appear once.
    """
    seen:   set[tuple] = set()
    result: list[dict] = []

    for item in items:
        key = (
            item.get("skill",  "").lower().strip(),
            item.get("market", "").lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def validator_node(state: MarketAgentState) -> dict:
    """
    LangGraph node — validates and compiles parallel research findings.

    Reads  : state["postings"], state["salaries"], state["trends"], state["skill_gaps"]
    Writes : state["validated_output"] (MarketAgentOutput)
    """
    logger.info("[validator] starting validation and consolidation")

    # --- 1. Normalize to dicts (items may already be dicts if nodes ran first) ---
    def _to_dict(item: object) -> dict:
        return item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)  # type: ignore[arg-type]

    postings_dicts = [_to_dict(p) for p in state.get("postings",   [])]
    salaries_dicts = [_to_dict(s) for s in state.get("salaries",   [])]
    trends_dicts   = [_to_dict(t) for t in state.get("trends",     [])]
    gaps_dicts     = [_to_dict(g) for g in state.get("skill_gaps", [])]

    # --- 2. Source validation ---
    # Skill gaps are derived (no source URL) — skip source check for them
    postings_dicts = [p for p in postings_dicts if has_valid_source(p)]
    salaries_dicts = [s for s in salaries_dicts if has_valid_source(s)]
    trends_dicts   = [t for t in trends_dicts   if has_valid_source(t)]

    # --- 3. Confidence filtering ---
    # Drop items the extraction passes weren't confident about
    postings_dicts = [p for p in postings_dicts if p.get("confidence", 0) >= MIN_CONFIDENCE]
    salaries_dicts = [s for s in salaries_dicts if s.get("confidence", 0) >= MIN_CONFIDENCE]
    trends_dicts   = [t for t in trends_dicts   if t.get("confidence", 0) >= MIN_CONFIDENCE]

    # --- 4. Deduplication ---
    postings_dicts = _dedup_postings(postings_dicts)
    salaries_dicts = _dedup_salaries(salaries_dicts)
    trends_dicts   = _dedup_trends(trends_dicts)
    gaps_dicts     = _dedup_gaps(gaps_dicts)

    # --- 5. Reconstruct Pydantic models ---
    # Safe because model_dump(mode="json") already converted HttpUrl to str
    try:
        final_postings = [JobPosting(**p)     for p in postings_dicts]
        final_salaries = [SalaryInsight(**s)  for s in salaries_dicts]
        final_trends   = [MarketTrend(**t)    for t in trends_dicts]
        final_gaps     = [SkillGap(**g)       for g in gaps_dicts]
    except Exception as e:
        logger.error(f"[validator] model reconstruction failed: {e}")
        raise

    # --- 6. Build final output ---
    validated_output = MarketAgentOutput(
        job_postings    = final_postings,
        salary_insights = final_salaries,
        market_trends   = final_trends,
        skill_gaps      = final_gaps,
    )

    logger.info(
        f"[validator] done — "
        f"{len(final_postings)} postings, "
        f"{len(final_salaries)} salaries, "
        f"{len(final_trends)} trends, "
        f"{len(final_gaps)} skill gaps"
    )

    return {"validated_output": validated_output.model_dump(mode="json")}