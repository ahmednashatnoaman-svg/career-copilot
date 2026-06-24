"""
nodes/trends.py — Market Trends Lane Node
=========================================

WHAT THIS FILE DOES
-------------------
Fetches market trends for every LaneQuery where lane == "trends".
Writes a list of validated MarketTrend objects to state["trends"].

HYBRID APPROACH
---------------
Two-pass extraction per snippet:

  Pass 1 — Deterministic (fast, free, no LLM)
    - Exact keyword matching against a known skills dictionary
    - Quick quality check: is the snippet long enough to be useful?
    - If snippet is clean and skills found → use directly, skip LLM

  Pass 2 — LLM (when deterministic insight is noisy or skills list is thin)
    - Summarizes raw title+snippet into one clean insight sentence
    - Infers skills from context (catches synonyms, implicit mentions)
    - Returns empty list when no skills signal exists (never invents)

FLOW PER QUERY
--------------
    1. Build cache key
    2. Cache hit  → deserialize cached MarketTrends
    3. Cache miss → search_trends()
    4. For each result: deterministic pass → LLM pass if needed
    5. Store validated results in cache
    6. Return {"trends": [...]}

TEAMMATES
---------
- To add skills to the dictionary: edit KNOWN_SKILLS below
- LLM model is set in .env (LLM_PROVIDER / LLM_MODEL) — see llm.py
- Cache TTL is TRENDS_TTL_HOURS in constants.py (default 168h / 1 week)
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from pydantic import BaseModel

from app.agents.market_research.llm import get_llm
from app.agents.market_research.schemas import LaneQuery, MarketTrend, Source
from app.agents.market_research.state import MarketAgentState
from app.agents.market_research.tools.cache import build_cache_key, get_cached, set_cache
from app.agents.market_research.tools.web_search import search_trends

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known skills dictionary — deterministic matching
# Add new skills here, they'll be picked up automatically
# ---------------------------------------------------------------------------

KNOWN_SKILLS: dict[str, str] = {
    # key = lowercase match pattern, value = display name
    "python":           "Python",
    "javascript":       "JavaScript",
    "typescript":       "TypeScript",
    "java":             "Java",
    "c++":              "C++",
    "c#":               "C#",
    "go":               "Go",
    "rust":             "Rust",
    "swift":            "Swift",
    "php":              "PHP",
    "ruby":             "Ruby",
    "sql":              "SQL",
    "html":             "HTML",
    "css":              "CSS",
    "react":            "React",
    "angular":          "Angular",
    "vue":              "Vue",
    "next.js":          "Next.js",
    "node.js":          "Node.js",
    "django":           "Django",
    "flask":            "Flask",
    "fastapi":          "FastAPI",
    "spring boot":      "Spring Boot",
    "pytorch":          "PyTorch",
    "tensorflow":       "TensorFlow",
    "keras":            "Keras",
    "pandas":           "Pandas",
    "numpy":            "NumPy",
    "scikit-learn":     "Scikit-learn",
    "aws":              "AWS",
    "azure":            "Azure",
    "gcp":              "GCP",
    "docker":           "Docker",
    "kubernetes":       "Kubernetes",
    "terraform":        "Terraform",
    "jenkins":          "Jenkins",
    "git":              "Git",
    "ci/cd":            "CI/CD",
    "machine learning": "Machine Learning",
    "deep learning":    "Deep Learning",
    "nlp":              "NLP",
    "computer vision":  "Computer Vision",
    "data science":     "Data Science",
    "ai":               "AI",
    "mlops":            "MLOps",
    "llm":              "LLM",
    "langchain":        "LangChain",
    "langgraph":        "LangGraph",
    "openai":           "OpenAI",
    "hugging face":     "Hugging Face",
    "fine-tuning":      "Fine-tuning",
    "rag":              "RAG",
    "vector database":  "Vector Database",
    "pinecone":         "Pinecone",
    "weaviate":         "Weaviate",
    "mongodb":          "MongoDB",
    "postgresql":       "PostgreSQL",
    "mysql":            "MySQL",
    "redis":            "Redis",
    "elasticsearch":    "Elasticsearch",
    "kafka":            "Kafka",
    "airflow":          "Airflow",
    "spark":            "Spark",
    "graphql":          "GraphQL",
    "rest api":         "REST API",
    "microservices":    "Microservices",
    "devops":           "DevOps",
    "agile":            "Agile",
    "scrum":            "Scrum",
    "system design":    "System Design",
    "backend":          "Backend",
    "frontend":         "Frontend",
    "fullstack":        "Full Stack",
    "cloud computing":  "Cloud Computing",
}

# Snippet must be at least this many characters to be worth processing
_MIN_SNIPPET_LENGTH = 80

# Need at least this many skills from deterministic pass to skip LLM
_MIN_SKILLS_TO_SKIP_LLM = 2


# ---------------------------------------------------------------------------
# Pass 1 — Deterministic skill extraction
# ---------------------------------------------------------------------------

def _deterministic_extract_skills(text: str, user_skills: list[str]) -> list[str]:
    """
    Match known skills against text using exact word boundary matching.
    Also includes user's own skills so they're always considered.
    Returns sorted list of display names.
    """
    text_lower = text.lower()
    found: set[str] = set()

    # Build combined skill set: known dictionary + user's skills
    combined: dict[str, str] = dict(KNOWN_SKILLS)
    for skill in user_skills:
        cleaned = skill.lower().strip()
        if cleaned and cleaned not in combined:
            combined[cleaned] = skill.strip()

    for pattern, display_name in combined.items():
        # Special characters need escaping (c++, c#, next.js etc.)
        escaped = re.escape(pattern)
        if any(c in pattern for c in ("+", "#", ".")):
            regex = escaped
        else:
            regex = r'\b' + escaped + r'\b'

        if re.search(regex, text_lower):
            found.add(display_name)

    return sorted(found)


def _is_useful_snippet(snippet: str) -> bool:
    """Check if snippet is long enough and not just a date/navigation fragment."""
    stripped = snippet.strip()
    if len(stripped) < _MIN_SNIPPET_LENGTH:
        return False
    # Filter out snippets that are mostly dates/numbers (navigation artifacts)
    word_count = len(stripped.split())
    if word_count < 10:
        return False
    return True


# ---------------------------------------------------------------------------
# Pass 2 — LLM enrichment
# ---------------------------------------------------------------------------

class TrendExtraction(BaseModel):
    """
    Structured output schema for LLM trend extraction.
    LLM must return None/empty when signal is absent — never invent.
    """
    insight:        str         # one clean sentence summarizing the trend
    related_skills: list[str]   # skills inferred from context
    confidence:     float = 0.6 # 0.0–1.0


_TREND_EXTRACTION_PROMPT = """
You are a job market analyst extracting structured data from search snippets.

Given the title and snippet below, return:

1. insight: ONE clear sentence summarizing the market trend.
   - Remove dates, URLs, publication metadata
   - Focus on what skills or roles are in demand and why
   - Example: "AI and MLOps skills are increasingly required for backend roles in Egypt"

2. related_skills: list of technical skills mentioned or strongly implied.
   - Include explicit mentions: "Python", "Docker", etc.
   - Include implied skills: "builds data pipelines" → Apache Airflow, Spark
   - Include implied skills: "LLM fine-tuning" → PyTorch, Hugging Face
   - Return empty list if no skills are mentioned or implied

3. confidence: your confidence this is a real market trend (0.0–1.0)
   - High (0.8+): clear trend claim with specific skills and context
   - Medium (0.5): vague or partially relevant
   - Low (0.3): mostly noise or unrelated

Title: {title}
Snippet: {snippet}
"""


def _llm_extract(title: str, snippet: str) -> TrendExtraction | None:
    """
    Ask the LLM to summarize and extract skills from a trend snippet.
    Returns None on failure so caller can fall back gracefully.
    """
    try:
        llm = get_llm()
        structured = llm.with_structured_output(TrendExtraction)
        result = structured.invoke(
            _TREND_EXTRACTION_PROMPT.format(
                title   = title[:200],
                snippet = snippet[:600],
            )
        )
        return result
    except Exception as e:
        logger.warning(f"[trends] LLM extraction failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Hybrid extraction — deterministic first, LLM when needed
# ---------------------------------------------------------------------------

def _extract_trend(
    title: str,
    snippet: str,
    user_skills: list[str],
) -> tuple[str, list[str], float]:
    """
    Run deterministic skill extraction first.
    Call LLM only when:
      - Snippet is noisy/short (not useful as raw insight)
      - Deterministic found fewer than _MIN_SKILLS_TO_SKIP_LLM skills

    Returns (insight, related_skills, confidence).
    """
    text = f"{title} {snippet}".strip()

    # Deterministic skills pass — always runs, free
    det_skills = _deterministic_extract_skills(text, user_skills)
    snippet_ok  = _is_useful_snippet(snippet)

    # Deterministic is enough: clean snippet + enough skills found
    if snippet_ok and len(det_skills) >= _MIN_SKILLS_TO_SKIP_LLM:
        # Clean up insight — remove date artifacts from the snippet
        insight = re.sub(r'^[\w]{3}\s+\d{1,2},\s+\d{4}\s*[–-]?\s*', '', snippet).strip()
        insight = insight[:300]
        logger.debug("[trends] deterministic extraction sufficient")
        return insight, det_skills, 0.7

    # LLM pass — snippet noisy or skills list thin
    logger.debug("[trends] calling LLM for enrichment")
    llm_result = _llm_extract(title, snippet)

    if llm_result and llm_result.insight:
        # Merge: LLM insight + union of both skill sets
        merged_skills = sorted(set(det_skills) | set(llm_result.related_skills))
        return llm_result.insight, merged_skills, llm_result.confidence

    # LLM failed — fall back to deterministic with raw insight
    raw_insight = f"{title} — {snippet[:200]}" if title else snippet[:200]
    return raw_insight, det_skills, 0.5


# ---------------------------------------------------------------------------
# Raw dict → Pydantic model
# ---------------------------------------------------------------------------

def _to_market_trend(raw: dict, user_skills: list[str]) -> MarketTrend | None:
    """Convert a raw search result dict into a MarketTrend model."""
    title   = raw.get("title",   "").strip()
    snippet = raw.get("snippet", "").strip()
    url     = raw.get("url",     "").strip()

    if not url:
        return None

    insight, skills, confidence = _extract_trend(title, snippet, user_skills)

    # Drop results with empty insight and no skills — pure noise
    if not insight and not skills:
        return None

    try:
        return MarketTrend(
            insight        = insight,
            related_skills = skills,
            source         = Source(
                name         = raw.get("source", "web_search"),
                url          = url,
                retrieved_at = datetime.now(UTC),
            ),
            confidence = round(confidence, 2),
        )
    except Exception as e:
        logger.warning(f"[trends] failed to build MarketTrend: {e}")
        return None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def trends_node(state: MarketAgentState) -> dict:
    """
    LangGraph node — fetches market trends for all trends-lane queries.

    Reads  : state["lane_queries"], state["input"].skills
    Writes : state["trends"]  (appended via reducer — see state.py)
    """
    all_trends: list[MarketTrend] = []

    queries: list[LaneQuery] = [
        q for q in state.get("lane_queries", [])
        if q.lane == "trends"
    ]

    if not queries:
        logger.warning("[trends] no trends queries found in lane_queries")
        return {"trends": []}

    # User's skills used to expand deterministic matching
    user_skills: list[str] = []
    if "input" in state and hasattr(state["input"], "skills"):
        user_skills = state["input"].skills

    for query in queries:
        cache_key = build_cache_key(
            role        = query.role,
            location    = query.location or "",
            market_mode = query.market_mode,
            lane        = "trends",
        )

        # 1. Cache check
        cached = get_cached(cache_key, lane="trends")
        if cached is not None:
            trends = [_to_market_trend(item, user_skills) for item in cached]
            all_trends.extend(t for t in trends if t)
            continue

        # 2. Cache miss — fetch
        logger.info(
            f"[trends] fetching: role={query.role!r} "
            f"mode={query.market_mode} location={query.location!r}"
        )
        raw_results = search_trends(
            role     = query.role,
            location = query.location or "",
        )

        # 3. Extract + convert
        trends = [_to_market_trend(r, user_skills) for r in raw_results]
        trends = [t for t in trends if t]

        # 4. Cache raw results
        if trends:
            set_cache(key=cache_key, data=raw_results, lane="trends")

        all_trends.extend(trends)
        logger.info(
            f"[trends] done: role={query.role!r} "
            f"mode={query.market_mode} → {len(trends)} trends"
        )

    return {"trends": all_trends}