# AI Career Copilot — System Design Spec

**Date:** 2026-06-24
**Status:** Approved design (pending user spec review) → next step: implementation plan
**Owner:** Ahmad Nashat
**Source repo:** `Ahmed-Aboalasaad/career-agent` (branches: `feature/cv-analysis-agent`, `feature/market_agent`, `feature/coaching_agent`)

---

## 1. Overview

AI Career Copilot is an end-to-end **multi-agent system** that assists a job seeker across the full lifecycle: understand the resume, build a knowledge base from uploaded documents, research the job market, match and rank jobs, detect skill gaps, coach for interviews, and generate tailored application materials — with a human approving every irreversible action.

This spec covers the **1-month "solid" deliverable**: a LangGraph **Supervisor multi-agent system** that integrates the three already-built agents into one standardized monorepo, adds the missing orchestration/RAG/HITL/persistence glue, exposes a FastAPI backend + Next.js dashboard, and ships containerized with Podman.

The build uses a **100% free / self-hostable stack** (Groq + Gemini free tiers, local HuggingFace BGE embeddings, self-hosted Postgres + Qdrant, Tavily + LangSmith free tiers).

### Decisions locked during brainstorming
| Decision | Choice |
|---|---|
| Target scope | Supervisor multi-agent system (from the 1–3.jpeg sketches) |
| Existing code | Integrate + standardize the 3 branches into one monorepo |
| Timeline | ~1 month, "solid" (real persistence + tests) |
| Interface | Full Next.js dashboard |
| Orchestration | **A**: LangGraph Supervisor + specialized agents as subgraphs |
| LLM/cost | Free only: Groq Llama 3, Gemini free, HF embeddings, free DBs |
| Application agent | Generate + **HITL-assisted** apply (no browser auto-submit) |

---

## 2. Requirements → design mapping (course rubric)

The course "Final Project Requirements" (req1–3) must all be satisfied. They map cleanly onto the supervisor system:

| Rubric item | Where it lives in this design |
|---|---|
| RAG retrieval from uploaded documents | RAG/Knowledge Agent + ingestion pipeline → Qdrant (§7) |
| Web search tool integration | Job/Market Research Agent → Tavily tool (§6.4, §8) |
| Multi-agent delegation (Deep Agents subagents) | Supervisor + 8 specialized subgraph agents + Critic + `AGENTS.md` (§5, §6) |
| Human-in-the-loop for critical decisions | LangGraph `interrupt()` gates on application send + critic escalation (§9) |
| LangSmith tracing enabled | Env-level tracing wraps the whole graph (§11) |
| Containerized with Podman | `Containerfile` (backend + frontend) + `podman-compose` (§12) |

---

## 3. Current state & gap analysis (what exists vs. what's missing)

**Already built (3 disconnected branches, 3 different layouts):**
- `feature/cv-analysis-agent` — CV/ATS analysis. FastAPI service, `app/core/{extraction,analysis}`, ATS scoring, LLM feedback, an `integration/graph_node.py` stub, good tests. Uses `pyproject.toml`. **Not yet a LangGraph agent — it's a service.**
- `feature/market_agent` — Job/Market research. Real **LangGraph** (planner → parallel postings/salaries/trends → skill_gap → validator), tools (Adzuna/Bayt/Upwork/Wuzzuf/web_search/rag_lookup), services (dedup/confidence/source_validation), `cache.py`. Flat layout, `requirements.txt`. **Best reference for the agent pattern.**
- `feature/coaching_agent` — Coaching. LangGraph + embeddings + memory + observability + rate_limit + docker-compose. `app/` layout, `requirements.txt`.

**The gap is integration, not features:**
1. No Supervisor/orchestrator, no shared state schema, no cross-agent memory.
2. No unified RAG store; no HITL wiring; no single container; no frontend.
3. Three incompatible structures (`pyproject` vs `requirements`; `app/core` vs flat vs `app/`) — they can't be imported together today.
4. The default branch is itself a feature branch — **there is no integrated `main`.**
5. Nothing in the repo yet satisfies the rubric's "Main Agent + subagents + Podman + HITL" shape.

---

## 4. Goals & non-goals

**Goals**
- One coherent monorepo integrating the 3 existing agents as subgraphs.
- A Supervisor that plans, routes, aggregates, and coordinates memory + HITL.
- Durable, resumable runs (Postgres checkpointer) with HITL that survives restarts.
- RAG over uploaded documents; web search; Critic/grounding loop.
- FastAPI backend (streaming) + Next.js dashboard.
- Fully containerized with Podman; tests + CI; LangSmith tracing.

**Non-goals (this month)**
- Browser auto-submit of applications (descoped to HITL-assisted generation).
- **Authenticated** scraping of LinkedIn/Glassdoor (ToS + anti-bot); we use their *public* pages via web search only — no login/CAPTCHA evasion.
- Kafka/Redis/K8s/Prometheus enterprise ops (PDF "future work").
- Full 11-agent build — we ship **8 specialists + Supervisor + Critic** (10 agents).
- Paid APIs (OpenAI/Anthropic) — free providers only.

---

## 5. Architecture

```
                         ┌─────────────────────────────┐
        User ───────────▶│   Next.js Dashboard (UI)    │
                         └──────────────┬──────────────┘
                                        │ REST + SSE/WebSocket
                         ┌──────────────▼──────────────┐
                         │     FastAPI backend (API)    │
                         │  upload · run · stream · HITL │
                         └──────────────┬──────────────┘
                                        │ invoke / resume
                         ┌──────────────▼──────────────┐
                         │   SUPERVISOR (LangGraph)     │
                         │  intent · plan · route · agg │
                         └──────────────┬──────────────┘
        ┌──────────┬──────────┬──────────┴──────────┬──────────┬──────────┐
        ▼          ▼          ▼                     ▼          ▼          ▼
   CV Analysis   RAG/KB    Market Research      Matching   Coaching   Application
   (subgraph)  (subgraph)   (subgraph)         (subgraph) (subgraph)  (gen+HITL)
        │          │          │                     │          │          │
        ▼          ▼          ▼                     ▼          ▼          ▼
   Portfolio/   Career                                              ┌──────────────┐
   GitHub       Planning  ───────────────────────────────────────▶ │    CRITIC    │
   (subgraph)  (subgraph)                                           │ (judge/loop) │
        └──────────┴───────────────────────────────────────────────┴──────────────┘
                                        │ shared state
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                                ▼
  Postgres checkpointer          LangGraph Store               Qdrant (per-user
  (durable threads + HITL)    (long-term user memory)          RAG vectors)
                                        │
                        Tools: Tavily web search · job boards · GitHub · email(draft)
                        LLM: Groq Llama 3.3/3.1 (+ Gemini 2.0 Flash fallback)
                        Embeddings: local HF BGE bge-small-en-v1.5
                        Tracing: LangSmith (wraps all)
```

**Control flow:** Supervisor detects intent → builds a plan → routes to one or more agents (sequential or fan-out) → agents write to shared state → **Critic** validates grounding ("loop if hallucinated", bounded retries) → Supervisor aggregates → at any critical action a **HITL `interrupt()`** pauses the run for human approval → resume on `Command(resume=...)` → final result streamed to UI.

---

## 6. Agents

Each agent is a compiled LangGraph **subgraph** exposing a typed `run(input) -> output` contract and registered as a node in the supervisor graph. "Source" = where the logic comes from.

### 6.0 Supervisor (new)
- **Responsibilities:** intent detection, task planning, agent routing (sequential/parallel), result aggregation, memory coordination, HITL coordination, retry budget.
- **Tools/Model:** Groq Llama 3.3 70B for planning/routing; structured output (Pydantic) for the routing decision.

### 6.1 CV Analysis Agent — *port `feature/cv-analysis-agent`*
- **Responsibilities:** parse resume (PyMuPDF/pdfplumber/python-docx), ATS score, extract skills/experience, strengths/weaknesses.
- **Integration:** wrap `app/core/pipeline.py` behind a subgraph node; reuse `integration/graph_node.py`.
- **Out:** `ResumeProfile { skills[], experience[], ats_score, strengths[], weaknesses[] }`.

### 6.2 RAG / Knowledge Agent — *new (reuse `market_agent/tools/rag_lookup.py`)*
- **Responsibilities:** own the per-user knowledge base; ingest uploaded docs (resume, certificates, portfolio, LinkedIn export); semantic retrieval to ground other agents.
- **Tools:** ingestion pipeline (§7), Qdrant client, local BGE embeddings.
- **Out:** retrieved chunks with citations; satisfies the **RAG rubric item**.

### 6.3 Job/Market Research Agent — *port `feature/market_agent`*
- **Responsibilities:** web + job-board research; postings, salaries, trends; skill-gap.
- **Integration:** move its LangGraph in as a subgraph; keep planner→parallel→skill_gap→validator; keep `cache.py`, dedup/confidence/source_validation.
- **Tools:** **Tavily** (primary, satisfies **web-search rubric item**); job boards behind feature flags (default off / Tavily fallback).
- **Out:** `JobPosting[]`, `MarketInsights`, `SkillGap`.

### 6.4 Job Matching Agent — *new (light)*
- **Responsibilities:** semantic match resume ↔ jobs, rank top-N, explain each match.
- **Tools:** BGE embeddings + HF cross-encoder reranker (free); Qdrant similarity.
- **Out:** `RankedMatch[] { job, score, rationale }`.

### 6.5 Coaching Agent — *port `feature/coaching_agent`*
- **Responsibilities:** interview prep, mock Q&A (behavioral + technical), feedback, career advice.
- **Integration:** move its graph + memory + observability into the monorepo.
- **Out:** `CoachingSession { questions[], feedback }`.

### 6.6 Application Agent — *new (generate + HITL)*
- **Responsibilities:** tailored CV, cover letter (≤400 words), application email; prepare submission package. **Stateless generation; does NOT persist; does NOT auto-submit.**
- **HITL:** emits an `interrupt()` with the draft package; human approves/edits before any "send".
- **Out:** `ApplicationPackage { tailored_cv, cover_letter, email, status }` where `status ∈ {DRAFT, APPROVED, SENT, HUMAN_REQUIRED}`.

### 6.7 Critic / Judge Agent — *new (from 3.jpeg)*
- **Responsibilities:** grounding/hallucination check on drafts and recommendations against retrieved evidence; "loop if hallucinated" with a bounded retry budget; escalate to HITL if still failing.
- **Out:** `CriticVerdict { grounded: bool, issues[], action ∈ {ACCEPT, REGENERATE, ESCALATE} }`.

### 6.8 Portfolio / GitHub Agent — *new (lean)*
- **Responsibilities:** analyze the user's GitHub (and portfolio links): top repos, languages, activity, README quality, project signal; produce portfolio strengths/gaps and concrete improvement suggestions; feed evidence to Matching, Application, and Critic.
- **Tools:** **GitHub REST API** (free `GITHUB_TOKEN`); optional repo README fetch; LLM summarization (Llama 3.1 8B for cheap extraction, 70B for the writeup).
- **Out:** `PortfolioReport { profile, top_projects[], languages[], strengths[], gaps[], suggestions[] }`.

### 6.9 Career Planning Agent — *new (lean)*
- **Responsibilities:** synthesize CV profile + skill gap + market trends + portfolio into a forward-looking plan: target role/level, 30/60/90-day learning roadmap, certifications, and a promotion/transition path.
- **Tools:** consumes other agents' state (no new external API); LLM reasoning (Llama 3.3 70B); RAG/market grounding so the Critic can validate it.
- **Out:** `CareerPlan { target_role, roadmap[], certifications[], milestones[] }`.

*Skill-Gap is delivered inside the Market agent (§6.3). The Critic grounds the Career Plan and Portfolio suggestions against retrieved evidence.*

---

## 7. RAG pipeline (uploaded documents)

**Ingest:** upload (PDF/docx) → parse (PyMuPDF / pdfplumber / python-docx) → chunk (recursive/semantic, ~500–800 tokens, overlap) → embed (**local `BAAI/bge-small-en-v1.5`** via sentence-transformers, no API key) → upsert to **Qdrant** with metadata `{ user_id, doc_type, source, chunk_id }`.

**Retrieve:** vector search top-k filtered by `user_id`; optional BM25 hybrid + cross-encoder rerank; return chunks + citations.

**Why bge-small:** ~130 MB vs ~1.3 GB for bge-large — keeps the container light and runs free on CPU; sufficient for resumes/certs/portfolio text.

---

## 8. Tools & job sources

**General tools**

| Tool | Provider | Notes |
|---|---|---|
| Web search | **Tavily** | Primary; rubric item; user has key. Also the fallback for any failed job source |
| Embeddings | local HF BGE | Free, no key |
| GitHub analysis | GitHub REST | Portfolio agent; free `GITHUB_TOKEN` |
| Email | Resend (draft) | Only if we actually send; otherwise draft-for-copy in UI |

**Job sources — unified behind a `JobSource` adapter interface** (`search(query, filters) -> JobPosting[]`, `insights(role, region) -> MarketInsights`). One adapter per site; each is a config flag; any failing source degrades gracefully to Tavily.

| Source | Integration class | Free key? | Status / risk |
|---|---|---|---|
| **Adzuna** | Official **API** | `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` (free) | ✅ Structured backbone; adapter exists (`market_agent/adzuna.py`) |
| **Wuzzuf** | Public-page scrape | none | ⚠️ Brittle; adapter exists; Tavily fallback |
| **Bayt / Upwork** | Public-page scrape | none | ⚠️ Brittle; adapters exist |
| **LinkedIn** | **Public pages via web search** (no auth scraping) | none | ⚠️ No usable free API + strong anti-bot → listings via Tavily/Firecrawl-public only |
| **Glassdoor** | **Public pages via web search** for salary/reviews/insights | none | ⚠️ No free API → insights via Tavily/Firecrawl-public only |
| *(optional)* SerpAPI / Firecrawl | Search/scrape API | free tier | Richer LinkedIn/Glassdoor public fetch if Tavily is thin |

> **Ethics/ToS:** we use only public pages and official APIs; no login-walled scraping, no CAPTCHA/anti-bot evasion. Salary/reviews from Glassdoor and listings from LinkedIn are surfaced through web search, attributed, and grounded by the Critic.

---

## 9. Human-in-the-loop (critical decisions)

Implemented with LangGraph `interrupt()` + Postgres checkpointer (so a paused run survives a container restart and resumes via `Command(resume=...)`).

1. **Before sending any application** (email/submit) — approve/edit cover letter + email. *(Primary HITL gate.)*
2. **Critic escalation** — if grounding fails after N regenerations, ask the human to confirm/correct.
3. **Job-shortlist approval** *(optional)* — approve which jobs to pursue before tailoring CVs.

Frontend renders each interrupt payload as an **approval card**; the user's decision resumes the graph.

---

## 10. LLM strategy (free tiers)

- **Reasoning / Supervisor / Critic / Coaching:** Groq **Llama 3.3 70B**.
- **Cheap high-volume nodes** (routing, extraction, classification): Groq **Llama 3.1 8B**.
- **Fallback / long-context / overflow:** **Gemini 2.0 Flash** (free tier).
- **Embeddings:** local BGE (free).
- **Provider router** (`llm/`) with model-per-task config, **exponential backoff**, and **fallback** across providers; reuse `coaching_agent/rate_limit.py` and `market_agent/cache.py`.

> **#1 risk:** free-tier RPM/TPM caps under multi-agent fan-out. Mitigations: small-model-for-cheap-nodes, response caching, provider fallback, and bounded Critic retries.

---

## 11. Backend, data model, observability

**FastAPI** (Pydantic v2). Endpoints (initial):
- `POST /documents` — upload + trigger ingestion.
- `POST /runs` — start a copilot run (intent + inputs); returns `run_id/thread_id`.
- `GET /runs/{id}/stream` — SSE token/step streaming.
- `POST /runs/{id}/resume` — answer a HITL interrupt.
- `GET /applications`, `GET /runs/{id}` — results/tracking.

**Persistence:** Postgres for (a) LangGraph **checkpointer**, (b) LangGraph **Store** (long-term memory), (c) app tables (`users`, `documents`, `jobs`, `matches`, `applications`, `runs`). SQLAlchemy + Alembic migrations. Uploaded files on a local volume (MinIO optional).

**Observability:** LangSmith tracing via env (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`); structured per-node logs (`node_name, status, duration, error, timestamp`) — reuse `coaching_agent/observability.py`.

---

## 12. Frontend & containerization

**Frontend:** Next.js (App Router) + Tailwind + shadcn/ui. Core pages: **Onboarding/Upload**, **Copilot chat** (streaming), **Matches**, **Skill Gap**, **Coaching**, **Applications tracker**, **HITL approval modals**. Talks to FastAPI via REST + SSE/WebSocket. Scope kept to the core flow (1 week).

**Containers (Podman):**
- `backend/Containerfile` (Python 3.12, uv).
- `frontend/Containerfile` (Node).
- `infra/compose.yaml` (podman-compose): `backend`, `frontend`, `postgres`, `qdrant` (+ optional `minio`). README documents `podman build` / `podman-compose up`.

---

## 13. Target monorepo structure

```
career-copilot/
  backend/
    app/
      main.py                  # FastAPI entry
      api/                     # routers: documents, runs, applications, hitl
      core/                    # config, logging, security
      orchestrator/
        supervisor.py          # supervisor StateGraph
        state.py               # CopilotState (typed shared state)
        router.py              # routing logic
        critic.py              # critic/judge node + loop
        hitl.py                # interrupt helpers
      agents/
        cv_analysis/           # ← feature/cv-analysis-agent
        rag/                   # knowledge base agent
        market_research/       # ← feature/market_agent
        matching/
        coaching/              # ← feature/coaching_agent
        application/           # generate + HITL
      rag/                     # ingestion, chunking, embeddings, qdrant client
      memory/                  # checkpointer + store + long-term memory
      llm/                     # provider router (groq/gemini), fallback, rate limit
      tools/                   # tavily web_search, job boards, github, email
      models/                  # pydantic + sqlalchemy
      db/                      # alembic migrations
    tests/
    pyproject.toml             # unified deps (uv)
    Containerfile
  frontend/                    # Next.js + Containerfile
  infra/compose.yaml           # podman-compose
  AGENTS.md                    # subagent behavior docs (rubric)
  docs/  .env.example  README.md
```

---

## 14. Integration plan for the 3 existing agents

1. Create a new integrated branch/monorepo (`main` does not exist yet).
2. **Standardize**: one `pyproject.toml` (uv), one settings/config, one `llm/` provider module, one logging/observability, one pytest suite.
3. **market_agent** → `agents/market_research/`: expose compiled subgraph + `run()`; keep tools/services/cache.
4. **cv-analysis-agent** → `agents/cv_analysis/`: wrap `pipeline.py` as a subgraph node (use its `graph_node.py`).
5. **coaching_agent** → `agents/coaching/`: move graph + memory + observability.
6. Port each branch's tests; add supervisor/RAG/critic/HITL integration tests.

---

## 15. Testing & CI ("solid")

- **Unit:** per-agent (port existing tests from the branches).
- **Integration:** supervisor happy path; Critic regenerate-loop; one HITL interrupt → resume cycle; RAG ingest→retrieve.
- **Contract:** Pydantic model round-trips.
- **CI:** GitHub Actions — lint (ruff) + tests (pytest) + `podman/docker build`.

---

## 16. Phasing (~4 weeks)

| Week | Focus | Deliverable |
|---|---|---|
| **1** | Foundation & monorepo unification: skeleton, unify deps/config/llm/observability, Podman compose (postgres+qdrant), FastAPI skeleton, Postgres checkpointer + Store, port the 3 agents (compiling, tests green), LangSmith wired | Each agent runs as a subgraph in the monorepo; container builds |
| **2** | Orchestration & RAG: Supervisor + routing + shared state; RAG ingestion + RAG agent; Critic loop; HITL interrupt on application send; **`JobSource` adapter interface** (Adzuna + Tavily fallback) | End-to-end analyze→research→match with critic gate |
| **3** | Matching + Application(gen+HITL) + Coaching integration; **Portfolio/GitHub agent** + **Career Planning agent** (lean); remaining job-source adapters (Wuzzuf/Bayt, LinkedIn/Glassdoor via web search); FastAPI endpoints + SSE streaming + HITL resume API | Full backend flow via API, all 8 specialists live |
| **4** | Next.js dashboard; long-term memory; GitHub Actions CI; docs (README + AGENTS.md + diagram); demo script; free-tier rate-limit hardening | Containerized full-stack demo |

---

## 17. API keys / `.env` (what you must provide)

**Required (all free):**
```
GROQ_API_KEY=            # primary LLM (Llama 3.3 70B / 3.1 8B)
GOOGLE_API_KEY=          # Gemini 2.0 Flash fallback
TAVILY_API_KEY=          # web search   (you have this)
LANGCHAIN_API_KEY=       # tracing      (you have this)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=career-copilot
```
**Now also required (free) for the added agents/sources:**
```
ADZUNA_APP_ID=           # Adzuna job API (free)
ADZUNA_APP_KEY=          # Adzuna job API (free)
GITHUB_TOKEN=            # Portfolio/GitHub agent (free PAT, read-only)
```
**No key (self-hosted via Podman):** Postgres, Qdrant, local BGE embeddings. **No key needed** for LinkedIn/Glassdoor/Wuzzuf/Bayt — surfaced via Tavily web search.
**Optional:** `HUGGINGFACEHUB_API_TOKEN` (only if using HF API instead of local embeddings), `SERPAPI_API_KEY` / `FIRECRAWL_API_KEY` (richer LinkedIn/Glassdoor public fetch), `RESEND_API_KEY` (only if e-mailing applications).

---

## 18. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | Free-tier RPM/TPM limits under fan-out | small-model cheap nodes, caching, provider fallback, bounded retries |
| 2 | No integrated `main` | create monorepo branch; port from 3 features |
| 3 | `pyproject` vs `requirements` conflict | standardize on uv/pyproject |
| 4 | CV agent is a service, not a graph | wrap via existing `graph_node.py` |
| 5 | Next.js dashboard in 1 week is tight | scope to core pages; reuse shadcn |
| 6 | bge-large image bloat | use bge-small-en-v1.5 |
| 7 | Application auto-apply brittleness | descoped to HITL-assisted generation |
| 8 | LinkedIn/Glassdoor: no free API + anti-bot + ToS | public pages via Tavily web search only; `JobSource` adapter + Tavily fallback; no auth scraping |
| 9 | Scope creep from 2 added agents (10 total) | keep Portfolio/Career-Planning **lean** single-purpose subgraphs; reuse other agents' state; no new external deps for Career Planning |

---

## 19. Success criteria

- `podman-compose up` brings up backend + frontend + postgres + qdrant.
- A user can upload a resume, ask "find me remote AI Engineer jobs in Europe," and get: ATS analysis → grounded job research (web search) → ranked matches → skill gap → coaching → a tailored application package **gated by a human approval**.
- A HITL interrupt pauses a run, survives a restart, and resumes correctly.
- LangSmith shows full traces; tests + CI pass.
- All six rubric items demonstrably satisfied.

---

## 20. Future work (post-month, from the PDF vision)

Next.js polish, Redis/Kafka, K8s, Prometheus/Grafana, browser auto-apply, visa-sponsorship analysis, recruiter CRM, voice interview coach, mobile app, deeper Glassdoor/LinkedIn integration if official API access is obtained.
