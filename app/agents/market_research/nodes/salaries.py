"""
nodes/salaries.py — Salaries Lane Node
======================================

WHAT THIS FILE DOES
-------------------
Fetches salary insights for every LaneQuery where lane == "salary".
Writes a list of validated SalaryInsight objects to state["salaries"].

HYBRID APPROACH
---------------
Two-pass extraction per snippet:

  Pass 1 — Deterministic (fast, free, no LLM)
    - Currency detection from known keywords
    - Year filter: reject numbers that look like years (1900–2099)
    - Quick confidence check: does snippet even mention salary?
    - If deterministic produces a clean result → use it, skip LLM

  Pass 2 — LLM (only when deterministic fails or is ambiguous)
    - Sends snippet + title to LLM with structured output schema
    - LLM reads in context so it understands "15k EGP monthly" correctly
    - Returns None fields when no salary signal exists (never invents)

FLOW PER QUERY
--------------
    1. Build cache key
    2. Cache hit  → deserialize cached SalaryInsights
    3. Cache miss → search_salaries()
    4. For each result: deterministic pass → LLM pass if needed
    5. Store validated results in cache
    6. Return {"salaries": [...]}

TEAMMATES
---------
- To change extraction logic: edit _deterministic_parse() or _llm_parse()
- LLM model is set in .env (LLM_PROVIDER / LLM_MODEL) — see llm.py
- Cache TTL is SALARIES_TTL_HOURS in constants.py
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from pydantic import BaseModel

from app.agents.market_research.llm import get_llm
from app.agents.market_research.schemas import LaneQuery, SalaryInsight, Source
from app.agents.market_research.state import MarketAgentState
from app.agents.market_research.tools.cache import build_cache_key, get_cached, set_cache
from app.agents.market_research.tools.web_search import search_salaries

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured output schema for LLM extraction
# ---------------------------------------------------------------------------

class SalaryExtraction(BaseModel):
    """
    What we ask the LLM to return.
    All fields optional — LLM must return None when signal is absent,
    never invent a number.
    """
    min_salary: float | None = None
    max_salary: float | None = None
    currency:   str   | None = None   # "EGP", "USD", "EUR", "GBP", "SAR" etc.
    confidence: float        = 0.5    # LLM self-rates 0.0–1.0


# ---------------------------------------------------------------------------
# Pass 1 — Deterministic
# ---------------------------------------------------------------------------

# Salary must be above this to be plausible (filters out page numbers, IDs)
_SALARY_FLOOR = 500


def _detect_currency(text: str) -> str:
    """Detect currency from known keywords. Defaults to USD."""
    t = text.lower()
    if any(k in t for k in ("egp", "جنيه", " le ", "l.e", "egyptian pound")):
        return "EGP"
    if any(k in t for k in ("sar", "riyal", "ريال")):
        return "SAR"
    if any(k in t for k in ("eur", "€", " euro")):
        return "EUR"
    if any(k in t for k in ("gbp", "£", " pound")):
        return "GBP"
    if any(k in t for k in ("aed", "dirham", "درهم")):
        return "AED"
    return "USD"


def _has_salary_signal(text: str) -> bool:
    """Quick check: does the text even mention salary?"""
    # Keywords that suggest a snippet is actually about salary
    _SALARY_SIGNALS = (
        "salary", "salaries", "per month", "monthly", "annual", "per year",
        "compensation", "راتب", "رواتب", "egp", "usd", "eur", "gbp",
        "k ", "/mo", "/yr", "package", "ctc",
    )
    t = text.lower()
    return any(signal in t for signal in _SALARY_SIGNALS)


def _is_year(n: float) -> bool:
    """Return True if a number looks like a calendar year."""
    return 1900 <= n <= 2099


def _deterministic_parse(
    text: str,
) -> tuple[float | None, float | None, str, float]:
    """
    Extract salary range using regex + rules.

    Returns (min_salary, max_salary, currency, confidence).
    Returns (None, None, currency, 0.0) when no clean result found.

    Confidence is higher when:
    - Two distinct numbers found (range, not just one value)
    - Explicit currency keyword present
    - Numbers are far enough apart to be a real range
    """
    currency = _detect_currency(text)

    # Expand "k" shorthand before parsing (15k → 15000)
    cleaned = re.sub(r'(\d+\.?\d*)\s*k\b', lambda m: str(float(m.group(1)) * 1000), text.lower())
    cleaned = cleaned.replace(",", "")

    # Extract all candidate numbers
    raw_numbers = [float(x) for x in re.findall(r'\b\d+(?:\.\d+)?\b', cleaned)]

    # Filter: remove years, remove implausibly small numbers
    numbers = [
        n for n in raw_numbers
        if not _is_year(n) and n >= _SALARY_FLOOR
    ]

    if not numbers:
        return None, None, currency, 0.0

    if len(numbers) >= 2:
        min_sal = min(numbers[:2])
        max_sal = max(numbers[:2])

        # If min == max, we only found the same number twice — treat as single
        if min_sal == max_sal:
            return min_sal, None, currency, 0.4

        confidence = 0.75 if currency != "USD" else 0.6
        return min_sal, max_sal, currency, confidence

    # Single number — less confident
    return numbers[0], None, currency, 0.4


# ---------------------------------------------------------------------------
# Pass 2 — LLM
# ---------------------------------------------------------------------------

_SALARY_EXTRACTION_PROMPT = """
You are a salary data extraction assistant.

Extract the salary range and currency from the snippet below.

Rules:
- Return ONLY what is explicitly stated in the text.
- If no salary is mentioned, return null for all fields.
- Never invent or estimate a number.
- Convert shorthand: "15k" → 15000, "1.5M" → 1500000
- Ignore years like 2024, 2025, 2026 — those are not salaries.
- Currency: detect from context (EGP, USD, EUR, GBP, SAR, AED).
  If unclear, return null for currency.
- confidence: your confidence that this is a real salary (0.0 to 1.0)

Text:
{text}
"""


def _llm_parse(text: str) -> SalaryExtraction:
    """
    Ask the LLM to extract salary from text using structured output.

    Returns SalaryExtraction with None fields if no salary found.
    Never raises — returns empty extraction on any failure.
    """
    try:
        llm = get_llm("fast")
        structured = llm.with_structured_output(SalaryExtraction)
        result = structured.invoke(
            _SALARY_EXTRACTION_PROMPT.format(text=text[:800])  # cap tokens
        )
        return result
    except Exception as e:
        logger.warning(f"[salaries] LLM extraction failed: {e}")
        return SalaryExtraction()


# ---------------------------------------------------------------------------
# Hybrid extraction — deterministic first, LLM if needed
# ---------------------------------------------------------------------------

def _extract_salary(
    title: str,
    snippet: str,
) -> tuple[float | None, float | None, str, float]:
    """
    Run deterministic pass first.
    Fall back to LLM only when deterministic is ambiguous or empty.

    Returns (min_salary, max_salary, currency, confidence).
    """
    text = f"{title} {snippet}".strip()

    # Fast exit: no salary signal at all → skip both passes
    if not _has_salary_signal(text):
        return None, None, "USD", 0.0

    # Pass 1: deterministic
    min_sal, max_sal, currency, confidence = _deterministic_parse(text)

    # Deterministic succeeded cleanly (range found, good confidence)
    if min_sal is not None and max_sal is not None and confidence >= 0.7:
        logger.debug("[salaries] deterministic extraction succeeded")
        return min_sal, max_sal, currency, confidence

    # Pass 2: LLM — deterministic was ambiguous or only found one number
    logger.debug("[salaries] falling back to LLM extraction")
    llm_result = _llm_parse(text)

    if llm_result.min_salary is not None:
        return (
            llm_result.min_salary,
            llm_result.max_salary,
            llm_result.currency or currency,
            llm_result.confidence,
        )

    # Both passes failed — return whatever deterministic found (may be None)
    return min_sal, max_sal, currency, confidence * 0.5


# ---------------------------------------------------------------------------
# Raw dict → Pydantic model
# ---------------------------------------------------------------------------

def _to_salary_insight(
    raw: dict,
    role: str,
    location: str,
) -> SalaryInsight | None:
    """Convert a raw search result dict into a SalaryInsight model."""
    title   = raw.get("title",   "").strip()
    snippet = raw.get("snippet", "").strip()
    url     = raw.get("url",     "").strip()

    if not url:
        return None

    min_sal, max_sal, currency, confidence = _extract_salary(title, snippet)

    # Drop results with no salary signal — they add noise
    if min_sal is None and max_sal is None:
        return None

    try:
        return SalaryInsight(
            role       = role,
            location   = location,
            min_salary = min_sal,
            max_salary = max_sal,
            currency   = currency,
            source     = Source(
                name         = raw.get("source", "web_search"),
                url          = url,
                retrieved_at = datetime.now(UTC),
            ),
            confidence = round(confidence, 2),
        )
    except Exception as e:
        logger.warning(f"[salaries] failed to build SalaryInsight: {e}")
        return None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def salaries_node(state: MarketAgentState) -> dict:
    """
    LangGraph node — fetches salary insights for all salary-lane queries.

    Reads  : state["lane_queries"]
    Writes : state["salaries"]  (appended via reducer — see state.py)
    """
    all_salaries: list[SalaryInsight] = []

    queries: list[LaneQuery] = [
        q for q in state.get("lane_queries", [])
        if q.lane == "salary"
    ]

    if not queries:
        logger.warning("[salaries] no salary queries found in lane_queries")
        return {"salaries": []}

    for query in queries:
        cache_key = build_cache_key(
            role        = query.role,
            location    = query.location or "",
            market_mode = query.market_mode,
            lane        = "salary",
        )

        # 1. Cache check
        cached = get_cached(cache_key, lane="salary")
        if cached is not None:
            salaries = [
                _to_salary_insight(item, query.role, query.location or "")
                for item in cached
            ]
            all_salaries.extend(s for s in salaries if s)
            continue

        # 2. Cache miss — fetch
        logger.info(
            f"[salaries] fetching: role={query.role!r} "
            f"mode={query.market_mode} location={query.location!r}"
        )
        raw_results = search_salaries(
            role     = query.role,
            location = query.location or "",
        )

        # 3. Extract + convert
        salaries = [
            _to_salary_insight(r, query.role, query.location or "")
            for r in raw_results
        ]
        salaries = [s for s in salaries if s]

        # 4. Cache raw results
        if salaries:
            set_cache(key=cache_key, data=raw_results, lane="salary")

        all_salaries.extend(salaries)
        logger.info(
            f"[salaries] done: role={query.role!r} "
            f"mode={query.market_mode} → {len(salaries)} insights"
        )

    return {"salaries": all_salaries}
