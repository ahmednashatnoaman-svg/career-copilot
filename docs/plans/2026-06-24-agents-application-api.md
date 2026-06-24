# Remaining Agents, Application & API — Implementation Plan (Plan 3 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox steps; TDD RED→GREEN→commit per Plan 1.

**Goal:** Add the four remaining specialist agents (Job Matching, Portfolio/GitHub, Career Planning, Application-generation), a pluggable `JobSource` adapter for real job sites, the relational data model, and the FastAPI surface (upload+ingest, start run, stream, resume HITL, applications) that the frontend will consume.

**Architecture:** Each agent is a node-shaped function `name_node(state: CopilotState) -> {"name": ...}` registered in the Supervisor (Plan 2). Job sourcing hides every site behind a `JobSource` ABC so the Market agent never depends on a specific site. FastAPI wraps the compiled supervisor: it streams graph events over SSE and resumes interrupts via `Command(resume=...)`. SQLAlchemy+Alembic persist users/documents/jobs/matches/applications/runs.

**Tech Stack:** LangGraph, FastAPI (SSE via `StreamingResponse`), SQLAlchemy 2 + Alembic, httpx, Tavily, GitHub REST, Groq/Gemini.

**Depends on:** Plan 1 (infra, ported agents) + Plan 2 (`CopilotState`, supervisor, HITL, RAG).

**Parallelism:** Tasks 3, 4, 5, 6 (the four agents) are mutually independent — dispatch them as parallel subagents. Task 1→2 (job sources) and Task 7→8 (data model→API) are sequential.

## Global Constraints

- All prior Global Constraints bind. Agents read/write only their namespaced `CopilotState` key.
- Job sites are accessed ONLY through `app.tools.jobsource.JobSource` implementations. NO authenticated scraping of LinkedIn/Glassdoor — public pages via Tavily/web search only; official API only for Adzuna. A failing source MUST degrade to the Tavily fallback, never crash the run.
- The Application agent GENERATES materials and prepares a submission; it NEVER auto-submits. The actual "send" is the HITL gate from Plan 2 (`application_send_node`).
- All external calls (job sites, GitHub, LLM) use `tenacity` retry with exponential backoff (free-tier rate limits).
- DB access via SQLAlchemy session dependency; migrations via Alembic only (no `create_all` in app code).
- SSE event shape is stable: `event: <node|token|interrupt|done>\ndata: <json>\n\n`.
- Branch: `feat/agents-api` off the Plan 2 branch.

---

## File structure

```
app/tools/jobsource/
  __init__.py base.py adzuna.py tavily_jobs.py linkedin.py glassdoor.py registry.py
app/agents/matching/agent.py
app/agents/portfolio/agent.py        + github_client.py
app/agents/career_planning/agent.py
app/agents/application/agent.py       + generators.py (cv, cover_letter, email)
app/models/db.py                      # SQLAlchemy models
app/db/                               # alembic env + versions/
app/api/{documents,runs,applications}.py
app/services/session.py               # DB session dependency
tests/  (one per module) + tests/integration/test_api.py
```

---

### Task 1: `JobSource` ABC + Adzuna + Tavily fallback + registry

**Files:** `app/tools/jobsource/{base,adzuna,tavily_jobs,registry}.py`, `tests/test_jobsource.py`.

**Interfaces — Produces:**
```python
class JobPosting(BaseModel):
    title: str; company: str; location: str | None; url: str
    salary: str | None = None; source: str; snippet: str | None = None

class JobSource(ABC):
    name: str
    @abstractmethod
    def search(self, query: str, *, location: str|None=None, limit: int=20) -> list[JobPosting]: ...

class AdzunaSource(JobSource):  # official API, ADZUNA_APP_ID/KEY; "adzuna"
class TavilyJobsSource(JobSource):  # web search fallback; "tavily"

def get_sources() -> list[JobSource]    # enabled sources from settings (Adzuna if keys present, else Tavily)
def search_all(query, *, location=None, limit=20) -> list[JobPosting]  # each source wrapped: failure → log + skip; if all fail → Tavily
```

- [ ] **Step 1 (RED):** tests: Adzuna parses a canned API JSON → `JobPosting[]`; `search_all` with a source that raises still returns results from the others (degradation); when no Adzuna keys, `get_sources()` falls back to Tavily. → FAIL.
- [ ] **Step 2 (GREEN):** Implement with httpx + tenacity; `search_all` wraps each `.search` in try/except. → PASS.
- [ ] **Step 3:** ruff; commit `feat: JobSource adapter with Adzuna + Tavily fallback and graceful degradation`.

---

### Task 2: LinkedIn + Glassdoor public-page sources (web search)

**Files:** `app/tools/jobsource/{linkedin,glassdoor}.py`, extend `tests/test_jobsource.py`.

**Interfaces — Produces:** `LinkedInSource` (Tavily query `site:linkedin.com/jobs ...` → `JobPosting`), `GlassdoorSource` (Tavily `site:glassdoor.com ... salary/reviews` → `JobPosting` + `salary` populated). Both registered behind config flags (default on, fallback-safe).

- [ ] **Step 1 (RED):** test that LinkedIn/Glassdoor sources build the correct `site:` query and map results to `JobPosting` with `source` set; a Tavily failure degrades silently. → FAIL.
- [ ] **Step 2 (GREEN):** Implement; add to `get_sources()`. NOTE in code comments: public pages only, no auth. → PASS.
- [ ] **Step 3:** ruff; commit `feat: linkedin + glassdoor public-page job sources via web search`.

---

### Task 3: Job Matching agent  *(parallel-safe)*

**Files:** `app/agents/matching/agent.py`, `tests/test_matching.py`.

**Interfaces — Produces:** `matching_node(state) -> {"matching": {"ranked": list[RankedMatch]}}` where `RankedMatch(job: JobPosting, score: float, rationale: str)`. Embeds the resume profile (`state["cv_analysis"]`) and each job (`state["market"]`) with `embed_texts`, scores by cosine, optionally reranks top-N with an LLM rationale.

- [ ] **Step 1 (RED):** test with canned cv+jobs and stubbed embeddings → `ranked` sorted desc by score, each with a rationale. → FAIL.
- [ ] **Step 2 (GREEN):** Implement (numpy-free cosine in pure Python over `embed_texts`). → PASS.
- [ ] **Step 3:** ruff; commit `feat: job matching agent (semantic rank + rationale)`.

---

### Task 4: Portfolio/GitHub agent  *(parallel-safe)*

**Files:** `app/agents/portfolio/{agent,github_client}.py`, `tests/test_portfolio.py`.

**Interfaces — Produces:** `github_client.fetch_profile(username, token) -> {repos, languages, stars, activity}` (GitHub REST, tenacity); `portfolio_node(state) -> {"portfolio": PortfolioReport}` with `PortfolioReport(profile, top_projects, languages, strengths, gaps, suggestions)`. LLM writes strengths/gaps from the fetched signal.

- [ ] **Step 1 (RED):** test `github_client` parses canned REST JSON; `portfolio_node` with stubbed client+LLM returns a `PortfolioReport`. → FAIL.
- [ ] **Step 2 (GREEN):** Implement; username sourced from `state` or profile; missing token → graceful "skipped" report. → PASS.
- [ ] **Step 3:** ruff; commit `feat: portfolio/github analysis agent`.

---

### Task 5: Career Planning agent  *(parallel-safe; no new external API)*

**Files:** `app/agents/career_planning/agent.py`, `tests/test_career_planning.py`.

**Interfaces — Produces:** `career_planning_node(state) -> {"career_plan": CareerPlan}` with `CareerPlan(target_role, roadmap: list[Milestone], certifications, milestones)`. Synthesizes `cv_analysis` + `market.skill_gaps` + `portfolio` from state via `get_llm("reason")`; output is grounded so the Critic can validate it.

- [ ] **Step 1 (RED):** test with canned upstream state + stubbed LLM → structured `CareerPlan` with ≥1 roadmap milestone. → FAIL.
- [ ] **Step 2 (GREEN):** Implement with `with_structured_output(CareerPlan)`. → PASS.
- [ ] **Step 3:** ruff; commit `feat: career planning agent (synthesis, no new deps)`.

---

### Task 6: Application generation agent  *(parallel-safe)*

**Files:** `app/agents/application/{agent,generators}.py`, `tests/test_application.py`.

**Interfaces — Produces:** `generators.tailor_cv(resume, job)`, `generators.cover_letter(resume, job, company)` (≤400 words), `generators.application_email(resume, job)`; `application_node(state) -> {"application": ApplicationPackage}` with `ApplicationPackage(tailored_cv, cover_letter, email, status="DRAFT")`. Pure generation — sets status `DRAFT`; the Plan 2 `application_send_node` handles the HITL approval/SEND transition.

- [ ] **Step 1 (RED):** test each generator (stubbed LLM) respects the word cap and returns non-empty; `application_node` returns a `DRAFT` package. → FAIL.
- [ ] **Step 2 (GREEN):** Implement. → PASS.
- [ ] **Step 3:** ruff; commit `feat: application generation agent (cv/cover letter/email, DRAFT only)`.

> After Tasks 3–6: register all four nodes in `app/orchestrator/supervisor.py` (extend Plan 2's builder + its node-set test). Commit `feat: register matching/portfolio/career/application nodes in supervisor`.

---

### Task 7: Relational model + Alembic migrations

**Files:** `app/models/db.py`, `app/services/session.py`, `app/db/env.py`, `app/db/versions/0001_init.py`, `tests/test_models.py`.

**Interfaces — Produces:** SQLAlchemy 2 models `User, Document, Job, Match, Application, Run` (+ `created_at`); `get_session()` FastAPI dependency; Alembic `0001_init` migration creating all tables. `Application.status` enum mirrors `ApplicationPackage.status` (`DRAFT/APPROVED/SENT/REJECTED/HUMAN_REQUIRED`).

- [ ] **Step 1 (RED):** test models import + a metadata check that all six tables and the `applications.status` enum exist in `Base.metadata`. → FAIL.
- [ ] **Step 2 (GREEN):** Implement models + session dependency; `alembic init`-style env reading `settings.database_url`; author `0001_init`. → PASS.
- [ ] **Step 3 (live, INFRA_UP=1):** `alembic upgrade head` against the compose Postgres; assert tables exist via `list_tables`. → PASS.
- [ ] **Step 4:** ruff; commit `feat: sqlalchemy models + alembic 0001 init migration`.

---

### Task 8: FastAPI endpoints (documents, runs, stream, resume, applications)

**Files:** `app/api/{documents,runs,applications}.py`, register routers in `app/main.py`, `tests/integration/test_api.py`.

**Interfaces — Produces (all under the compiled supervisor + Postgres checkpointer):**
- `POST /documents` (multipart) → save file, create `Document`, `ingest_document(...)` → `{doc_id, chunks}`.
- `POST /runs` `{user_id, message, doc_ids}` → start a thread; returns `{run_id, thread_id}` (persists a `Run`).
- `GET /runs/{thread_id}/stream` → `StreamingResponse` (SSE) of `supervisor.stream(..., stream_mode="updates")`; emits `node`/`token`/`interrupt`/`done` events; on interrupt emits the `hitl_request`.
- `POST /runs/{thread_id}/resume` `{decision}` → `Command(resume=decision)`; continues the stream/returns final.
- `GET /applications?user_id=` → list `Application` rows.

- [ ] **Step 1 (RED):** `test_api.py` (TestClient): `/health` still ok; `POST /runs` returns ids (supervisor stubbed/fast); `/runs/{id}/stream` yields at least a `done` event; `POST /documents` with a tiny text file returns `chunks>0` (ingest stubbed). → FAIL.
- [ ] **Step 2 (GREEN):** Implement routers; build the supervisor once at startup with `checkpointer_cm()`; SSE generator translates graph stream chunks to the stable event shape. → PASS.
- [ ] **Step 3 (live, INFRA_UP=1):** end-to-end: upload a resume → start a run "find AI engineer jobs and tailor an application" → consume stream until an `interrupt` (application_send) → `POST resume {approved:true}` → assert an `Application` row with `status=APPROVED`. → PASS.
- [ ] **Step 4:** ruff; commit `feat: fastapi endpoints for documents, runs, SSE streaming, HITL resume, applications`.

---

## Plan 3 self-review

- **Spec coverage:** JobSource/LinkedIn/Glassdoor/Adzuna (§8) ✓ T1–2; Matching (§6.4) ✓ T3; Portfolio/GitHub (§6.8) ✓ T4; Career Planning (§6.9) ✓ T5; Application gen + HITL handoff (§6.6,§9) ✓ T6; data model (§11) ✓ T7; API + SSE + resume (§11) ✓ T8.
- **Placeholders:** none; every task has interfaces + test gates.
- **Type consistency:** `JobPosting`, `RankedMatch`, `PortfolioReport`, `CareerPlan`, `ApplicationPackage(status)` align with Plan 2's `CopilotState` namespaced keys and the `application_send_node` contract.
- **Risk:** free-tier rate limits under fan-out + many job sources → tenacity backoff + Tavily fallback + Plan 4 caching. No auth scraping (ToS-safe).
