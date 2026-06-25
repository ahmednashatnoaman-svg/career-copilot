# AI Career Copilot

A **supervisor multi-agent system** that guides a job seeker end-to-end: it analyzes the CV, builds a RAG knowledge base from uploaded documents, researches the live job market, matches and ranks opportunities, detects skill gaps, coaches for interviews, and generates tailored application materials — with a **human approving every irreversible action**.

Built with **LangGraph** (orchestration + durable state), **FastAPI**, a **100% free** model stack (**Groq** Llama 3 primary, **Google Gemini** fallback, local **fastembed** BGE embeddings), self-hosted **Postgres** + **Qdrant**, **Tavily** web search, and **LangSmith** tracing — all containerized with **Podman**.

> This repository is the **integration** of three previously separate agents (CV Analysis, Market Research, Coaching), originally built on feature branches of
> [`Ahmed-Aboalasaad/career-agent`](https://github.com/Ahmed-Aboalasaad/career-agent), unified here into one standardized monorepo behind a Supervisor.

## Status

| Phase | Scope | State |
|---|---|---|
| **1 — Foundation** | Monorepo unification, config/LLM/embeddings, Postgres+Qdrant, FastAPI, 3 agents ported as subgraphs, LangSmith, Containerfile | ✅ Complete |
| **2 — Orchestration** | `CopilotState`, Supervisor + router, RAG pipeline, Critic loop, durable HITL interrupt/resume | ✅ Complete |
| **3 — Agents & API** | Matching, Portfolio/GitHub, Career-Planning, Application agents; `JobSource` adapters; SQLAlchemy/Alembic; SSE + HITL endpoints | ✅ Complete |
| **4 — Frontend & Release** | Next.js dashboard + approval modals, long-term memory, CI, free-tier hardening, full Podman compose | ✅ Complete |

See [`docs/specs/`](docs/specs/) for the design spec and [`docs/plans/`](docs/plans/) for the four implementation plans.

## Architecture

```
User → FastAPI → Supervisor (LangGraph)
                   ├─ CV Analysis   ├─ RAG/Knowledge   ├─ Market Research
                   ├─ Job Matching  ├─ Coaching        ├─ Portfolio/GitHub
                   ├─ Career Plan   └─ Application (generate + HITL)
                          │  Critic (loop-if-hallucinated) gate
        Postgres checkpointer + Store   ·   Qdrant (per-user RAG)
        Tools: Tavily web search · Adzuna/LinkedIn/Glassdoor (JobSource) · GitHub
```

## Quickstart

```bash
uv sync                                            # install deps (creates .venv)
cp .env.example .env                               # fill in free keys (Groq, Gemini, Tavily, LangSmith)
podman-compose -f infra/compose.yaml up -d         # Postgres + Qdrant + backend + frontend
# API at http://localhost:8000/health
# Dashboard at http://localhost:3000
```

To run the backend locally (dev mode, without containers):
```bash
uv run uvicorn app.main:app --reload               # API at http://localhost:8000/health
uv run pytest                                      # unit + smoke (infra tests skip without INFRA_UP=1)
```

To run the demo end-to-end:
```bash
bash scripts/demo.sh                               # requires stack up + keys in .env
```

Required free API keys (`.env`): `GROQ_API_KEY`, `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `LANGCHAIN_API_KEY` (+ `ADZUNA_APP_ID/KEY`, `GITHUB_TOKEN` for job sourcing & portfolio analysis). Postgres, Qdrant, and embeddings are keyless.

## Repository layout

```
app/
  core/        config, qdrant client, tracing
  llm/         multi-provider router (groq/gemini, reason/fast tasks, backoff)
  rag/         fastembed embeddings (RAG pipeline lands in Phase 2)
  memory/      Postgres checkpointer + Store factories
  orchestrator/ CopilotState (Supervisor lands in Phase 2)
  agents/      cv_analysis · market_research · coaching  (+ more in Phase 3)
  api/         FastAPI app + /health
infra/compose.yaml   backend · postgres · qdrant (Podman)
backend/Containerfile
docs/specs · docs/plans   design + roadmap
```

## License

See repository owner. Agents originally authored across `Ahmed-Aboalasaad/career-agent` feature branches.
