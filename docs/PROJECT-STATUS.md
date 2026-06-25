# Project Status

**As of:** Plan 4 complete · branch `feat/foundation-monorepo` · **147 passed, 8 skipped** (infra-gated), ruff clean.

## ✅ Complete

| Phase | What shipped | Tests |
|---|---|---|
| **Plan 1 — Foundation** | Unified monorepo, `core/config`, `llm/provider` (Groq/Gemini/Azure + `max_tokens`), `rag/embeddings` (fastembed BGE), Postgres checkpointer + Store, Qdrant client, FastAPI `/health`, LangSmith tracing, Containerfile + `infra/compose.yaml`; **3 agents ported** (cv_analysis, market_research, coaching) | ✅ all green |
| **Plan 2 — Orchestration** | `CopilotState`, RAG pipeline (chunking→ingest→Qdrant→retriever→RAG agent), Supervisor graph + router, Critic bounded loop, HITL `interrupt`/resume gate | ✅ all green |
| **Plan 3 — Agents + API** | `JobSource` adapters (Adzuna API + Tavily fallback + LinkedIn/Glassdoor public-page), 4 new agents (matching, portfolio/github, career_planning, application-gen), all registered in the Supervisor; SQLAlchemy models + Alembic `0001_init`; FastAPI endpoints (`/documents`, `/runs`, `/runs/{id}/stream` SSE, `/runs/{id}/resume`, `/applications`) | ✅ all green |
| **Plan 4 — Frontend & Release** | Next.js 15.3 dashboard (6 pages: onboarding, copilot, matches, coaching, applications, root); HITL `ApprovalModal` (focus-trap, edit mode); long-term memory via `PostgresStore`; free-tier hardening (cache + fallbacks + fast-model routing); GitHub Actions CI (3 jobs); Podman compose; Azure OpenAI provider; HITL contract aligned | ✅ all green |

## Post-Plan 4 fixes applied

| Fix | File | Commit |
|---|---|---|
| Real API keys written to `.env` (gitignored) | `.env` | — |
| Azure OpenAI added as third provider | `app/llm/provider.py`, `app/core/config.py`, `pyproject.toml` | — |
| HITL contract: `resumeRun` sent `{decision: "..."}` (double-wrap) instead of flat `{approved: bool}` | `frontend/lib/api.ts`, `frontend/app/copilot/page.tsx` | — |
| Hardening tests: `monkeypatch.delenv` doesn't override `.env` file → changed to `setenv("")` | `tests/test_llm_hardening.py` | — |

## ⚠️ Known limitations

- **SSE is buffered, not incremental** — `portfolio_node` is `async def`, so LangGraph runs an asyncio bridge in the threadpool, buffering all frames before flushing. Fix: convert `github_client.py` + `portfolio_node` to synchronous (requires updating 5 tests).
- **8 infra-gated tests** require a live Postgres + Qdrant stack (`INFRA_UP=1`). Run with `podman-compose -f infra/compose.yaml up -d`.
- **HITL e2e not yet run with real keys** — the contract fix above aligns backend and frontend; needs a live run to validate.
- **Google API key format** — the provided key (`AQ.Ab8RN6KSTmmWz...`) is not a standard Gemini Studio key; Gemini fallback will gracefully degrade to Azure/Groq.

## How to run

```bash
# Backend only (dev mode)
cp .env.example .env  # or edit existing .env with real keys
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Full stack
podman-compose -f infra/compose.yaml up -d
# API at http://localhost:8000  · Dashboard at http://localhost:3000

# Tests
uv run pytest                           # 147 unit + smoke (8 infra-gated skipped)
INFRA_UP=1 uv run pytest                # all 155 including live DB/Qdrant

# CI
git push feat/foundation-monorepo       # triggers GitHub Actions (3 jobs)
```

## Required keys (`.env`)

| Key | Source | Required |
|---|---|---|
| `GROQ_API_KEY` | console.groq.com | Yes (primary LLM) |
| `GOOGLE_API_KEY` | aistudio.google.com | Optional (Gemini fallback) |
| `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | Azure AI Foundry | Optional (third provider) |
| `TAVILY_API_KEY` | tavily.com | Yes (web search) |
| `LANGCHAIN_API_KEY` | smith.langchain.com | Optional (tracing) |
| `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` | developer.adzuna.com | Optional (job search) |
| `GITHUB_TOKEN` | github.com/settings/tokens | Optional (portfolio agent) |
