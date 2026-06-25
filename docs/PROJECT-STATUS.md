# Project Status & Next-Session Handoff

**As of:** end of Plan 3 · branch `feat/foundation-monorepo` · 84 commits · **129 passed, 7 skipped** (skips = infra-gated live tests), ruff clean.

## ✅ Complete

| Phase | What shipped | Tests |
|---|---|---|
| **Plan 1 — Foundation** | Unified monorepo, `core/config`, `llm/provider` (Groq/Gemini + `max_tokens`), `rag/embeddings` (fastembed BGE), Postgres checkpointer + Store, Qdrant client, FastAPI `/health`, LangSmith tracing, Containerfile + `infra/compose.yaml`; **3 agents ported** (cv_analysis, market_research, coaching) | all green |
| **Plan 2 — Orchestration** | `CopilotState`, RAG pipeline (chunking→ingest→Qdrant→retriever→RAG agent), Supervisor graph + router, Critic bounded loop, HITL `interrupt`/resume gate | all green (live e2e P2T10 deferred) |
| **Plan 3 — Agents + API** | `JobSource` adapters (Adzuna API + Tavily fallback + LinkedIn/Glassdoor public-page), 4 new agents (matching, portfolio/github, career_planning, application-gen), all registered in the Supervisor; SQLAlchemy models + Alembic `0001_init`; FastAPI endpoints (`/documents`, `/runs`, `/runs/{id}/stream` SSE, `/runs/{id}/resume`, `/applications`) | all green (live e2e deferred) |

Each task was implemented TDD-first and reviewed by a second agent (spec + quality), with fixes applied for every Critical/Important finding.

## ⬜ Next (Plan 4 — Frontend & Release)
See [`docs/plans/2026-06-24-frontend-productionization.md`](plans/2026-06-24-frontend-productionization.md): Next.js dashboard (upload, streaming copilot chat, matches, coaching, applications, **HITL approval modals**), long-term memory via `PostgresStore`, free-tier hardening (backoff + cache + fast-model routing), and the final whole-branch review.

## 🔧 Deferred infra pass (batch — needs a healthy Podman)
The earlier disk-full event corrupted the Podman VM's overlay storage. To unblock live validation:
1. Fix Podman (`podman system reset` — **global**, wipes all images/containers/volumes; our volumes are empty test DBs) or recreate the machine.
2. `podman-compose -f infra/compose.yaml up -d` (Postgres + Qdrant).
3. Run the **7 infra-gated tests** with `INFRA_UP=1` (RAG isolation, checkpointer round-trip, Alembic upgrade, supervisor live run, **P2T10 HITL-survives-restart**, API e2e).
4. `podman build -f backend/Containerfile -t career-copilot-backend .`.

## ⚠️ Known limitations to address next session
- **SSE is buffered, not incremental** (`app/api/runs.py`): the portfolio node uses an `asyncio.run()` bridge, so the graph is run sync-in-threadpool and frames are collected before flushing. Fix: make the portfolio GitHub client **sync** (drop `httpx.AsyncClient`), then register `portfolio_node` as a normal sync node and stream incrementally (or use a queue bridge).
- **P2T10** (HITL pause survives a container restart) is written but unrun — needs live Postgres.
- **Cross-agent enrichment** in the supervisor wrappers is minimal (e.g., market wrapper uses empty skills; coaching gets an empty profile) — wire CV/profile state into downstream agents.
- Minor test-polish items are recorded in commit history / review reports.

## How to resume
- Work continues on `feat/foundation-monorepo`; PRs are open on both repos (personal `#1`, career-agent `#1`) and update on push.
- Plan 4 briefs can be regenerated from `docs/plans/2026-06-24-frontend-productionization.md`.
- Required free keys for live runs: `GROQ_API_KEY`, `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `LANGCHAIN_API_KEY` (+ `ADZUNA_APP_ID/KEY`, `GITHUB_TOKEN`).
