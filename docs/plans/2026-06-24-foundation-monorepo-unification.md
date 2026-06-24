# Foundation & Monorepo Unification — Implementation Plan (Plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up one unified, installable `career-copilot/` monorepo where the three existing agents (CV, Market, Coaching) each run as a compiled LangGraph subgraph behind one config/LLM/persistence layer, with Postgres + Qdrant running under Podman, a FastAPI healthcheck, and LangSmith tracing — all green under `pytest`.

**Architecture:** A single `app/` Python package (uv/pyproject). Shared infra in `app/core` (config), `app/llm` (provider router), `app/memory` (Postgres checkpointer + Store), `app/rag` (embeddings client). Each ported agent lives under `app/agents/<name>/` and exposes one compiled graph + a node-shaped adapter. Podman Compose runs Postgres + Qdrant. No Supervisor yet — that is Plan 2.

**Tech Stack:** Python 3.12, uv, LangGraph 1.2.6+, LangChain (groq/google/openai/anthropic/ollama), langgraph-checkpoint-postgres, Qdrant + fastembed (`bge-small-en-v1.5`), FastAPI + uvicorn, pydantic v2 + pydantic-settings, psycopg[binary,pool], pytest, ruff, Podman.

## Global Constraints

- Python `>=3.12`. Package root is `app/` — all intra-repo imports are absolute from `app` (e.g. `from app.llm.provider import get_llm`). NO flat imports.
- Free providers only: Groq (primary), Google Gemini (fallback). NEVER add `openai`/`anthropic` as required runtime keys. Keep their LangChain adapters installed (optional) but unused by default.
- LLM access ONLY via `app.llm.provider.get_llm(...)`. Never import `ChatGroq`/`ChatGoogleGenerativeAI` directly inside a node.
- Embeddings ONLY via `app.rag.embeddings.get_embedder()` (fastembed, model `BAAI/bge-small-en-v1.5`). No `sentence-transformers`, no torch.
- Config ONLY via `app.core.config.get_settings()` (pydantic-settings, reads `.env`). No `os.getenv` scattered in nodes.
- Every commit message uses Conventional Commits (`feat:`, `chore:`, `test:`, `refactor:`).
- Containers are built with **Podman** and described with a `Containerfile` (not `Dockerfile`). Compose file is `infra/compose.yaml`, run with `podman-compose`.
- Source branches for porting (read-only): `origin/feature/market_agent`, `origin/feature/cv-analysis-agent`, `origin/feature/coaching_agent` in the sibling clone at `../career-agent`.

---

## File structure produced by this plan

```
career-copilot/
  pyproject.toml                 # unified deps (uv)
  .env.example
  .gitignore
  ruff.toml
  README.md
  infra/compose.yaml             # podman-compose: postgres + qdrant
  app/
    __init__.py
    main.py                      # FastAPI entry
    api/__init__.py
    api/health.py                # GET /health
    core/__init__.py
    core/config.py               # Settings (pydantic-settings)
    core/clients.py              # qdrant client factory
    llm/__init__.py
    llm/provider.py              # get_llm(task=...) multi-provider router
    memory/__init__.py
    memory/checkpointer.py       # Postgres checkpointer + Store factories
    rag/__init__.py
    rag/embeddings.py            # fastembed get_embedder()
    agents/__init__.py
    agents/market_research/...   # ported from feature/market_agent
    agents/cv_analysis/...       # ported from feature/cv-analysis-agent
    agents/coaching/...          # ported from feature/coaching_agent
  backend/Containerfile          # Podman image for the backend
  tests/
    conftest.py
    test_config.py
    test_llm_provider.py
    test_health.py
    test_embeddings.py
    integration/test_infra.py    # skipped unless INFRA_UP=1
    test_agents_smoke.py
```

---

### Task 1: Repo scaffold + unified `pyproject` + tooling

**Files:**
- Create: `career-copilot/pyproject.toml`, `career-copilot/ruff.toml`, `career-copilot/.gitignore`, `career-copilot/.env.example`, `career-copilot/app/__init__.py`, `career-copilot/tests/conftest.py`, `career-copilot/README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: an installable package `app`; `uv run pytest` and `uv run ruff check` work.

- [ ] **Step 1: Create the directory and package marker**

```bash
mkdir -p "career-copilot/app" "career-copilot/tests"
printf '"""career-copilot backend package."""\n' > career-copilot/app/__init__.py
```

- [ ] **Step 2: Write `career-copilot/pyproject.toml`**

```toml
[project]
name = "career-copilot"
version = "0.1.0"
description = "AI Career Copilot — supervisor multi-agent system"
requires-python = ">=3.12"
dependencies = [
  # --- orchestration / LLM ---
  "langgraph>=1.2.6",
  "langgraph-prebuilt>=1.1.0",
  "langgraph-checkpoint-postgres>=3.1.0",
  "langchain>=1.3.4",
  "langchain-core>=1.4.8",
  "langchain-groq>=1.1.3",
  "langchain-google-genai>=2.0.0",
  "langsmith>=0.8.18",
  # --- api ---
  "fastapi>=0.138.0",
  "uvicorn[standard]>=0.49.0",
  "python-multipart>=0.0.32",
  # --- config / db ---
  "pydantic>=2.13.4",
  "pydantic-settings>=2.14.1",
  "psycopg[binary,pool]>=3.3.4",
  "python-dotenv>=1.2.1",
  # --- rag / vector ---
  "qdrant-client>=1.12.0",
  "fastembed>=0.4.2",
  # --- document parsing (cv agent) ---
  "pymupdf>=1.27.0",
  "python-docx>=1.2.0",
  "pdfplumber>=0.11.0",
  # --- web search / scraping (market agent) ---
  "ddgs>=9.14.4",
  "tavily-python>=0.5.0",
  "beautifulsoup4>=4.15.0",
  "lxml>=6.1.0",
  "httpx>=0.28.1",
  "requests>=2.34.0",
  "tenacity>=9.1.4",
  "tiktoken>=0.13.0",
]

[dependency-groups]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=1.4.0",
  "ruff>=0.6.0",
  "httpx>=0.28.1",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-q"

[tool.uv]
package = false
```

- [ ] **Step 3: Write `career-copilot/ruff.toml`, `.gitignore`, `.env.example`, `README.md`**

`ruff.toml`:
```toml
line-length = 100
target-version = "py312"
[lint]
select = ["E", "F", "I", "UP", "B"]
ignore = ["E501"]
```

`.gitignore`:
```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
data/
```

`.env.example`:
```dotenv
# --- LLM (free) ---
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
LLM_MODEL_FAST=llama-3.1-8b-instant
GROQ_API_KEY=
GOOGLE_API_KEY=
# --- web search ---
TAVILY_API_KEY=
# --- tracing ---
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=career-copilot
# --- datastores (match infra/compose.yaml) ---
DATABASE_URL=postgresql://career:career@127.0.0.1:5432/career
QDRANT_URL=http://127.0.0.1:6333
# --- job sources / agents (free) ---
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
GITHUB_TOKEN=
```

`README.md`: one short paragraph + `uv sync` / `uv run pytest` / `podman-compose -f infra/compose.yaml up -d` quickstart.

- [ ] **Step 4: Create the package + install**

Run:
```bash
cd career-copilot && uv sync
```
Expected: a `.venv` is created and dependencies resolve without error.

- [ ] **Step 5: Add an empty conftest and verify the test runner works**

`tests/conftest.py`:
```python
"""Shared pytest fixtures."""
```
Run: `cd career-copilot && uv run pytest`
Expected: `no tests ran` (exit 0/5), no import errors. Then `uv run ruff check .` → passes.

- [ ] **Step 6: Commit**

```bash
cd career-copilot && git init -q && git add -A && git commit -q -m "chore: scaffold career-copilot monorepo with unified pyproject"
```

---

### Task 2: Unified configuration (`app/core/config.py`)

**Files:**
- Create: `app/core/__init__.py`, `app/core/config.py`, `tests/test_config.py`
- Reference (read-only): `../career-agent` → `git show origin/feature/coaching_agent:app/settings.py`

**Interfaces:**
- Produces: `get_settings() -> Settings` (cached). `Settings` fields: `llm_provider: str`, `llm_model: str`, `llm_model_fast: str`, `groq_api_key: str|None`, `google_api_key: str|None`, `tavily_api_key: str|None`, `database_url: str`, `qdrant_url: str`, `langchain_project: str`, `adzuna_app_id: str|None`, `adzuna_app_key: str|None`, `github_token: str|None`.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from app.core.config import get_settings

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_provider == "groq"
    assert s.llm_model_fast  # has a default
    assert s.qdrant_url.startswith("http")
    assert s.database_url.endswith("/db")
```

- [ ] **Step 2: Run it, expect failure**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.config`.

- [ ] **Step 3: Implement `app/core/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Career Copilot"
    app_env: str = "development"

    # LLM
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_model_fast: str = "llama-3.1-8b-instant"
    groq_api_key: str | None = None
    google_api_key: str | None = None

    # tools
    tavily_api_key: str | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    github_token: str | None = None

    # datastores
    database_url: str = "postgresql://career:career@127.0.0.1:5432/career"
    qdrant_url: str = "http://127.0.0.1:6333"

    # tracing
    langchain_project: str = "career-copilot"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```
Also create `app/core/__init__.py` (empty docstring).

- [ ] **Step 4: Run the test, expect pass**

Run: `uv run pytest tests/test_config.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add app/core tests/test_config.py && git commit -q -m "feat: unified pydantic-settings config"
```

---

### Task 3: Unified LLM provider router (`app/llm/provider.py`)

**Files:**
- Create: `app/llm/__init__.py`, `app/llm/provider.py`, `tests/test_llm_provider.py`
- Reference (read-only): `git show origin/feature/market_agent:llm.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces: `get_llm(task: Literal["reason","fast"] = "reason", temperature: float = 0.0) -> BaseChatModel`. `task="fast"` selects `settings.llm_model_fast`; `"reason"` selects `settings.llm_model`. Provider chosen by `settings.llm_provider` (`groq` | `google`).

- [ ] **Step 1: Write the failing test** (no network — assert construction + model id)

`tests/test_llm_provider.py`:
```python
from app.core.config import get_settings
from app.llm.provider import get_llm

def test_get_llm_groq_reason(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    llm = get_llm("reason")
    assert llm is not None
    # langchain-groq exposes .model_name
    assert "llama-3.3-70b" in getattr(llm, "model_name", getattr(llm, "model", ""))

def test_get_llm_fast_picks_small(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    llm = get_llm("fast")
    assert "8b" in getattr(llm, "model_name", getattr(llm, "model", ""))
```

- [ ] **Step 2: Run it, expect failure**

Run: `uv run pytest tests/test_llm_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: app.llm.provider`.

- [ ] **Step 3: Implement `app/llm/provider.py`**

```python
from typing import Literal
from langchain_core.language_models import BaseChatModel
from app.core.config import get_settings

Task = Literal["reason", "fast"]


def get_llm(task: Task = "reason", temperature: float = 0.0) -> BaseChatModel:
    s = get_settings()
    model = s.llm_model_fast if task == "fast" else s.llm_model

    if s.llm_provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=temperature, api_key=s.groq_api_key)

    if s.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        gmodel = "gemini-2.0-flash" if task == "fast" else "gemini-2.0-flash"
        return ChatGoogleGenerativeAI(model=gmodel, temperature=temperature, api_key=s.google_api_key)

    raise ValueError(f"Unsupported LLM_PROVIDER: {s.llm_provider!r}")
```
Create `app/llm/__init__.py` re-exporting `get_llm`.

- [ ] **Step 4: Run the test, expect pass**

Run: `uv run pytest tests/test_llm_provider.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add app/llm tests/test_llm_provider.py && git commit -q -m "feat: unified multi-provider LLM router (groq/gemini, reason/fast tasks)"
```

---

### Task 4: Embeddings client (`app/rag/embeddings.py`)

**Files:**
- Create: `app/rag/__init__.py`, `app/rag/embeddings.py`, `tests/test_embeddings.py`

**Interfaces:**
- Produces: `get_embedder() -> TextEmbedding` (cached, fastembed, `BAAI/bge-small-en-v1.5`); `embed_texts(texts: list[str]) -> list[list[float]]`; constant `EMBED_DIM = 384`.

- [ ] **Step 1: Write the failing test**

`tests/test_embeddings.py`:
```python
import pytest
from app.rag.embeddings import embed_texts, EMBED_DIM

@pytest.mark.slow
def test_embed_texts_shape():
    vecs = embed_texts(["python backend engineer", "data scientist"])
    assert len(vecs) == 2
    assert len(vecs[0]) == EMBED_DIM == 384
```

- [ ] **Step 2: Run it, expect failure**

Run: `uv run pytest tests/test_embeddings.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `app/rag/embeddings.py`**

```python
from functools import lru_cache
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


@lru_cache
def get_embedder() -> TextEmbedding:
    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [vec.tolist() for vec in get_embedder().embed(texts)]
```

- [ ] **Step 4: Run the test, expect pass**

Run: `uv run pytest tests/test_embeddings.py -v`
Expected: PASS (first run downloads the small ONNX model once).

- [ ] **Step 5: Commit**

```bash
git add app/rag tests/test_embeddings.py && git commit -q -m "feat: fastembed bge-small embeddings client"
```

---

### Task 5: Infra — Podman Compose (Postgres + Qdrant) + Qdrant client

**Files:**
- Create: `infra/compose.yaml`, `app/core/clients.py`, `tests/integration/__init__.py`, `tests/integration/test_infra.py`

**Interfaces:**
- Produces: `get_qdrant() -> QdrantClient` (cached, from `settings.qdrant_url`).

- [ ] **Step 1: Write `infra/compose.yaml`**

```yaml
services:
  postgres:
    image: docker.io/library/postgres:16
    environment:
      POSTGRES_USER: career
      POSTGRES_PASSWORD: career
      POSTGRES_DB: career
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  qdrant:
    image: docker.io/qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrantdata:/qdrant/storage"]
volumes:
  pgdata:
  qdrantdata:
```

- [ ] **Step 2: Implement `app/core/clients.py`**

```python
from functools import lru_cache
from qdrant_client import QdrantClient
from app.core.config import get_settings


@lru_cache
def get_qdrant() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url)
```

- [ ] **Step 3: Write the integration test (skipped unless infra is up)**

`tests/integration/test_infra.py`:
```python
import os
import pytest

pytestmark = pytest.mark.skipif(os.getenv("INFRA_UP") != "1", reason="infra not running")

def test_qdrant_reachable():
    from app.core.clients import get_qdrant
    assert get_qdrant().get_collections() is not None

def test_postgres_reachable():
    import psycopg
    from app.core.config import get_settings
    with psycopg.connect(get_settings().database_url, connect_timeout=3) as conn:
        assert conn.execute("select 1").fetchone()[0] == 1
```
Create empty `tests/integration/__init__.py`.

- [ ] **Step 4: Bring infra up and run the integration test**

Run:
```bash
podman-compose -f infra/compose.yaml up -d
INFRA_UP=1 uv run pytest tests/integration/test_infra.py -v
```
Expected: both PASS. (If `podman-compose` is unavailable, `podman compose` is an acceptable equivalent.)

- [ ] **Step 5: Commit**

```bash
git add infra app/core/clients.py tests/integration && git commit -q -m "feat: podman compose (postgres+qdrant) and qdrant client"
```

---

### Task 6: Memory — Postgres checkpointer + Store factories (`app/memory/checkpointer.py`)

**Files:**
- Create: `app/memory/__init__.py`, `app/memory/checkpointer.py`, add a unit test in `tests/test_memory.py`
- Reference (read-only): `git show origin/feature/coaching_agent:app/graph.py` (uses `PostgresSaver`)

**Interfaces:**
- Produces: `checkpointer_cm()` → context manager yielding a `PostgresSaver` (calls `.setup()` once); `store_cm()` → context manager yielding a `PostgresStore`. Both read `settings.database_url`.

- [ ] **Step 1: Write the failing unit test (no DB needed — assert the factory shape)**

`tests/test_memory.py`:
```python
from app.memory.checkpointer import checkpointer_cm, store_cm

def test_factories_are_context_managers():
    assert hasattr(checkpointer_cm(), "__enter__")
    assert hasattr(store_cm(), "__enter__")
```

- [ ] **Step 2: Run it, expect failure**

Run: `uv run pytest tests/test_memory.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement `app/memory/checkpointer.py`**

```python
from contextlib import contextmanager
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from app.core.config import get_settings


@contextmanager
def checkpointer_cm():
    with PostgresSaver.from_conn_string(get_settings().database_url) as cp:
        cp.setup()
        yield cp


@contextmanager
def store_cm():
    with PostgresStore.from_conn_string(get_settings().database_url) as store:
        store.setup()
        yield store
```

- [ ] **Step 4: Run the unit test, expect pass**

Run: `uv run pytest tests/test_memory.py -v` → PASS.

- [ ] **Step 5: (Infra-gated) verify a real checkpoint round-trip**

Add to `tests/integration/test_infra.py`:
```python
def test_checkpointer_setup():
    from app.memory.checkpointer import checkpointer_cm
    with checkpointer_cm() as cp:
        assert cp is not None
```
Run: `INFRA_UP=1 uv run pytest tests/integration/test_infra.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add app/memory tests/test_memory.py tests/integration/test_infra.py && git commit -q -m "feat: postgres checkpointer + store factories"
```

---

### Task 7: FastAPI skeleton + `/health` (`app/main.py`, `app/api/health.py`)

**Files:**
- Create: `app/api/__init__.py`, `app/api/health.py`, `app/main.py`, `tests/test_health.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces: ASGI app `app.main:app`; `GET /health -> {"status":"ok","app":<app_name>}`.

- [ ] **Step 1: Write the failing test**

`tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

- [ ] **Step 2: Run it, expect failure**

Run: `uv run pytest tests/test_health.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement the router and app**

`app/api/health.py`:
```python
from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}
```
`app/main.py`:
```python
from fastapi import FastAPI
from app.api.health import router as health_router

app = FastAPI(title="AI Career Copilot")
app.include_router(health_router)
```

- [ ] **Step 4: Run the test, expect pass**

Run: `uv run pytest tests/test_health.py -v` → PASS. Then `uv run uvicorn app.main:app --port 8000` and `curl localhost:8000/health` → ok.

- [ ] **Step 5: Commit**

```bash
git add app/api app/main.py tests/test_health.py && git commit -q -m "feat: fastapi skeleton with /health"
```

---

### Task 8: Port the Market Research agent → `app/agents/market_research/`

**Files:**
- Create: `app/agents/__init__.py`, `app/agents/market_research/` (ported tree), `app/agents/market_research/adapter.py`, `tests/test_agents_smoke.py` (start it here)
- Source (read-only): `origin/feature/market_agent` (flat layout: `graph.py`, `state.py`, `schemas.py`, `nodes/`, `tools/`, `services/`, `prompts.py`, `constants.py`)

**Interfaces:**
- Produces: `app.agents.market_research.graph.market_agent_graph` (compiled); `app.agents.market_research.adapter.market_node(state) -> {"market": MarketAgentOutput}`.

- [ ] **Step 1: Copy the source tree into the package**

```bash
SRC=../career-agent
mkdir -p app/agents/market_research/{nodes,tools,services}
touch app/agents/__init__.py app/agents/market_research/__init__.py
git -C "$SRC" archive origin/feature/market_agent | tar -x -C app/agents/market_research \
  --exclude='tests' --exclude='README.md' --exclude='.env.example' --exclude='.gitignore' --exclude='requirements.txt'
```

- [ ] **Step 2: Rewrite flat imports to absolute package imports**

In every `.py` under `app/agents/market_research/`, prefix first-party modules with the package path. Run:
```bash
cd app/agents/market_research
# module names that are local to this agent:
for mod in state schemas constants prompts llm nodes tools services; do
  grep -rl --include='*.py' -E "(^|[^.])\b(from|import) ${mod}\b" . | while read -r f; do
    sed -i '' -E "s/\bfrom ${mod}\b/from app.agents.market_research.${mod}/g; s/\bimport ${mod}\b/import app.agents.market_research.${mod}/g" "$f"
  done
done
cd -
```
Then **manually verify** `graph.py`, `state.py`, and each `nodes/*.py` import line now reads e.g. `from app.agents.market_research.nodes.planner import planner_node`. (The agent's own `llm.py` is replaced in Step 3, so leave its import to be redirected there.)

- [ ] **Step 3: Redirect the agent's LLM usage to the shared router**

Replace `app/agents/market_research/llm.py` contents with a thin shim so nodes that do `from app.agents.market_research.llm import get_llm` keep working:
```python
"""Shim: market_research nodes use the shared provider router."""
from app.llm.provider import get_llm  # noqa: F401
```

- [ ] **Step 4: Write the adapter**

`app/agents/market_research/adapter.py`:
```python
from app.agents.market_research.graph import market_agent_graph
from app.agents.market_research.schemas import MarketAgentInput


def market_node(state: dict) -> dict:
    """Supervisor-facing node: expects state['market_input']: MarketAgentInput."""
    result = market_agent_graph.invoke({"input": state["market_input"]})
    return {"market": result["validated_output"]}
```

- [ ] **Step 5: Write the smoke test (compiles + imports, no network)**

`tests/test_agents_smoke.py`:
```python
def test_market_graph_compiles():
    from app.agents.market_research.graph import market_agent_graph
    assert market_agent_graph is not None
    # compiled graph exposes get_graph()
    assert market_agent_graph.get_graph().nodes
```

- [ ] **Step 6: Run it, expect pass**

Run: `uv run pytest tests/test_agents_smoke.py::test_market_graph_compiles -v`
Expected: PASS. If it fails on an import, fix the specific module path and re-run.

- [ ] **Step 7: Commit**

```bash
git add app/agents/market_research app/agents/__init__.py tests/test_agents_smoke.py \
  && git commit -q -m "feat: port market research agent as subgraph under app.agents"
```

---

### Task 9: Port the CV Analysis agent → `app/agents/cv_analysis/`

**Files:**
- Create: `app/agents/cv_analysis/` (ported `app/core`, `app/schemas.py`, `app/integration/graph_node.py`)
- Source (read-only): `origin/feature/cv-analysis-agent` (`app/core/...`, `app/schemas.py`, `app/integration/graph_node.py`)

**Interfaces:**
- Produces: `app.agents.cv_analysis.graph_node.cv_analysis_node(state) -> {"cv_analysis": CVAnalysisResponse}` (the adapter already exists upstream); `CVAnalysisResponse` from `app.agents.cv_analysis.schemas`.

- [ ] **Step 1: Copy the relevant subtree**

```bash
SRC=../career-agent
mkdir -p app/agents/cv_analysis
touch app/agents/cv_analysis/__init__.py
git -C "$SRC" archive origin/feature/cv-analysis-agent app/core app/schemas.py app/integration \
  | tar -x -C app/agents/cv_analysis --strip-components=1
```
This yields `app/agents/cv_analysis/{core,schemas.py,integration}`.

- [ ] **Step 2: Rewrite imports from `app.core`/`app.schemas` to the new package root**

```bash
cd app/agents/cv_analysis
grep -rl --include='*.py' -E "app\.(core|schemas|integration)" . | while read -r f; do
  sed -i '' -E "s/\bapp\.core\b/app.agents.cv_analysis.core/g; \
                s/\bapp\.schemas\b/app.agents.cv_analysis.schemas/g; \
                s/\bapp\.integration\b/app.agents.cv_analysis.integration/g" "$f"
done
cd -
```

- [ ] **Step 3: Redirect the CV agent's Groq call to the shared router**

Open `app/agents/cv_analysis/core/analysis/llm_feedback.py`; replace its direct Groq client construction with:
```python
from app.llm.provider import get_llm
# ... where it previously built a groq client:
llm = get_llm("reason", temperature=0.2)
response_text = llm.invoke(prompt).content
```
Keep the existing prompt-building and Pydantic parsing; only the model call changes.

- [ ] **Step 4: Add a smoke test (standalone analysis on plain text, LLM mocked)**

Append to `tests/test_agents_smoke.py`:
```python
def test_cv_node_importable():
    from app.agents.cv_analysis.integration.graph_node import cv_analysis_node, CVAnalysisInputState
    assert callable(cv_analysis_node)

def test_cv_standalone_text(monkeypatch):
    from app.agents.cv_analysis.core import pipeline
    # stub the LLM feedback so the test needs no network
    monkeypatch.setattr(
        pipeline, "run_tailored_analysis", pipeline.run_tailored_analysis, raising=True
    )
    from app.agents.cv_analysis.integration.graph_node import cv_analysis_node
    monkeypatch.setattr(
        "app.agents.cv_analysis.core.analysis.llm_feedback.get_llm",
        lambda *a, **k: type("M", (), {"invoke": lambda self, p: type("R", (), {"content": '{"strengths":[],"weaknesses":[],"suggestions":[]}'})()})(),
        raising=False,
    )
    out = cv_analysis_node({"resume_text": "Jane Doe. Python, FastAPI, LangGraph. 3 years backend."})
    assert "cv_analysis" in out
    assert out["cv_analysis"].entities is not None
```

- [ ] **Step 5: Run, fix module paths until pass**

Run: `uv run pytest tests/test_agents_smoke.py -k cv -v`
Expected: PASS. spaCy model: if `en_core_web_sm` is required, add `python -m spacy download en_core_web_sm` to README setup and guard extraction to degrade gracefully when absent (the upstream code already uses rule-based fallback).

- [ ] **Step 6: Commit**

```bash
git add app/agents/cv_analysis tests/test_agents_smoke.py \
  && git commit -q -m "feat: port cv analysis agent as subgraph node under app.agents"
```

---

### Task 10: Port the Coaching agent → `app/agents/coaching/`

**Files:**
- Create: `app/agents/coaching/` (ported `app/*.py`)
- Source (read-only): `origin/feature/coaching_agent` (`app/{graph,llm,memory,observability,prompts,rate_limit,schemas,settings,embeddings}.py`)

**Interfaces:**
- Produces: `app.agents.coaching.graph.build_coaching_graph(checkpointer) -> CompiledGraph` (or the existing module-level compiled graph); `ChatRequest`/`ChatResponse` from `app.agents.coaching.schemas`.

- [ ] **Step 1: Copy the coaching app modules**

```bash
SRC=../career-agent
mkdir -p app/agents/coaching
touch app/agents/coaching/__init__.py
git -C "$SRC" archive origin/feature/coaching_agent app \
  | tar -x -C app/agents/coaching --strip-components=1
```

- [ ] **Step 2: Rewrite `app.<module>` imports to `app.agents.coaching.<module>`**

```bash
cd app/agents/coaching
for mod in graph llm memory observability prompts rate_limit schemas settings embeddings; do
  grep -rl --include='*.py' -E "app\.${mod}\b" . | while read -r f; do
    sed -i '' -E "s/\bapp\.${mod}\b/app.agents.coaching.${mod}/g" "$f"
  done
done
cd -
```

- [ ] **Step 3: Make coaching use shared config + LLM + checkpointer**

- In `app/agents/coaching/settings.py`: delete the local `Settings`; replace with `from app.core.config import get_settings, Settings` re-export so existing `from app.agents.coaching.settings import Settings` keeps working.
- In `app/agents/coaching/llm.py`: back `LLMService` with the shared router — its chat method calls `get_llm("reason", temperature=...)` from `app.llm.provider`.
- In `app/agents/coaching/graph.py`: do NOT compile with its own `PostgresSaver` at import time; expose `build_coaching_graph(checkpointer=None)` that compiles with the passed checkpointer (the Supervisor will pass the shared one in Plan 2). Keep a lazy module-level `coaching_graph = None` default.

- [ ] **Step 4: Smoke test (graph builds without a live DB)**

Append to `tests/test_agents_smoke.py`:
```python
def test_coaching_graph_builds():
    from app.agents.coaching.graph import build_coaching_graph
    g = build_coaching_graph(checkpointer=None)
    assert g.get_graph().nodes
```

- [ ] **Step 5: Run, expect pass**

Run: `uv run pytest tests/test_agents_smoke.py -k coaching -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add app/agents/coaching tests/test_agents_smoke.py \
  && git commit -q -m "feat: port coaching agent under app.agents with shared infra"
```

---

### Task 11: LangSmith tracing wiring + full smoke suite + backend Containerfile

**Files:**
- Create: `backend/Containerfile`, `app/core/tracing.py`; modify `app/main.py`
- Verify: all of `tests/` green

**Interfaces:**
- Produces: `configure_tracing()` (sets LangSmith env from settings, idempotent), called on FastAPI startup; a buildable Podman image.

- [ ] **Step 1: Implement tracing config**

`app/core/tracing.py`:
```python
import os
from app.core.config import get_settings

def configure_tracing() -> None:
    s = get_settings()
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", s.langchain_project)
    # LANGCHAIN_API_KEY is read from the environment / .env by langsmith directly.
```
Wire it in `app/main.py`:
```python
from app.core.tracing import configure_tracing

@app.on_event("startup")
def _startup() -> None:
    configure_tracing()
```

- [ ] **Step 2: Add a test that tracing config is idempotent**

`tests/test_tracing.py`:
```python
from app.core.tracing import configure_tracing
import os

def test_configure_tracing_sets_project(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    configure_tracing()
    assert os.environ["LANGCHAIN_PROJECT"] == "career-copilot"
```
Run: `uv run pytest tests/test_tracing.py -v` → PASS.

- [ ] **Step 3: Write the backend Containerfile (Podman)**

`backend/Containerfile`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install uv
COPY pyproject.toml ./
RUN uv pip install --system -r <(uv pip compile pyproject.toml 2>/dev/null) || uv sync --no-dev
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Build the image with Podman**

Run:
```bash
podman build -f backend/Containerfile -t career-copilot-backend .
```
Expected: image builds; `podman run --rm -p 8000:8000 --env-file .env career-copilot-backend` serves `/health`.

- [ ] **Step 5: Run the FULL test suite (unit; infra-gated tests skipped)**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all unit + smoke tests PASS; integration tests SKIP (unless `INFRA_UP=1`); ruff clean.

- [ ] **Step 6: Commit + add backend service to compose**

Add a `backend` service to `infra/compose.yaml` (build context `.`, `Containerfile` path `backend/Containerfile`, `env_file: .env`, `depends_on: [postgres, qdrant]`, ports `8000:8000`). Then:
```bash
git add backend/Containerfile app/core/tracing.py app/main.py tests/test_tracing.py infra/compose.yaml \
  && git commit -q -m "feat: langsmith tracing wiring + backend Containerfile + compose service"
```

---

## Plan 1 self-review

- **Spec coverage (Plan-1 scope):** monorepo unification (§13, §14) ✓ Tasks 1,8–10; unified config/LLM (§10) ✓ Tasks 2–3; Postgres checkpointer + Store (§11) ✓ Task 6; Qdrant + embeddings for RAG (§7) ✓ Tasks 4–5; FastAPI skeleton (§11) ✓ Task 7; Podman container (§12) ✓ Tasks 5,11; LangSmith (§11) ✓ Task 11. Deferred to later plans by design: Supervisor/Critic/HITL (Plan 2), remaining agents + Application + API endpoints (Plan 3), Next.js (Plan 4).
- **Placeholders:** none — every step has real code/commands.
- **Type consistency:** `get_llm(task, temperature)`, `get_settings()`, `cv_analysis_node(state)->{"cv_analysis":...}`, `market_node(state)->{"market":...}`, `build_coaching_graph(checkpointer)` are used consistently across tasks.
- **Known risk:** `sed -i ''` syntax is macOS/BSD (matches this dev environment). On Linux use `sed -i`. The import-rewrite steps require manual verification (called out in Tasks 8–10).

---

## Plans 2–4 (index — written when we reach them)

- **Plan 2 — Orchestration, RAG, Critic, HITL:** `CopilotState`, Supervisor StateGraph + router, Critic node + bounded regenerate loop, RAG ingestion pipeline (upload→chunk→fastembed→Qdrant) + RAG agent, HITL `interrupt()` on application-send, wire Postgres checkpointer into the supervisor. Deliverable: end-to-end analyze→research→match with a critic gate and one HITL pause/resume.
- **Plan 3 — Remaining agents + Application + API:** Job Matching, Portfolio/GitHub, Career Planning, Application (generate + HITL); `JobSource` adapter interface (Adzuna + Tavily fallback + LinkedIn/Glassdoor via web search); FastAPI endpoints (`/documents`, `/runs`, `/runs/{id}/stream`, `/runs/{id}/resume`, `/applications`) with SSE streaming. Deliverable: full backend flow via API, all 8 specialists live.
- **Plan 4 — Frontend + productionize:** Next.js dashboard (upload, copilot chat/stream, matches, skill gap, coaching, applications, HITL approval modals), long-term memory via Store, GitHub Actions CI (ruff+pytest+podman build), docs (README + AGENTS.md + architecture diagram), free-tier rate-limit hardening (backoff + caching + fast-model routing). Deliverable: containerized full-stack demo.
