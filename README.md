# AI Career Copilot

[![CI](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/ci.yml)
[![Deploy Frontend](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-vercel.yml/badge.svg)](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-vercel.yml)
[![Deploy Backend](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-hf.yml/badge.svg)](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-hf.yml)

A **supervisor multi-agent system** that guides a job seeker end-to-end: analyzes CV, builds a RAG knowledge base from uploaded documents, researches the live job market, matches and ranks opportunities, detects skill gaps, coaches for interviews, and generates tailored application materials — with a **human approving every irreversible action**.

## Live Deployment

| Service | URL |
|---|---|
| **Frontend** (Vercel) | https://career-copilot-fawn.vercel.app |
| **Backend API** (HF Spaces) | https://AhmedNashat1-career-copilot-api.hf.space |
| **API Docs** (Swagger) | https://AhmedNashat1-career-copilot-api.hf.space/docs |
| **HF Space** | https://huggingface.co/spaces/AhmedNashat1/career-copilot-api |
| **Tracing** (LangSmith) | https://smith.langchain.com → project *CareerFlow* |

## Architecture

```
Browser (Next.js 15 · Vercel)
    │  Supabase Google OAuth  ·  JWT on every request
    ▼
FastAPI (Hugging Face Spaces)
    │  jwt_auth_middleware → verify Supabase JWT
    ▼
Supervisor (LangGraph · CopilotState)
    ├─ CV Analysis          ← fastembed chunks → Qdrant RAG
    ├─ Market Research      ← Tavily · Adzuna · Glassdoor · LinkedIn
    ├─ Job Matching         ← cosine similarity over Qdrant vectors
    ├─ Coaching             ← long-term memory in Postgres
    ├─ Interview Prep       ← context-aware Q&A
    ├─ Portfolio Analyzer   ← GitHub API
    ├─ Career Planning      ← structured roadmap generation
    └─ Application Writer   ← cover letter + CV tailoring
           │  Critic loop (halt if hallucinated)
           │  HITL interrupt → frontend ApprovalModal → resume
           ▼
    Postgres (Supabase)     ·  checkpointer + long-term store
    Qdrant Cloud            ·  per-user RAG vectors (career_docs)
    LangSmith               ·  full trace on every run
```

## Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph (supervisor graph, HITL interrupt/resume) |
| **LLM — primary** | Groq `llama-3.3-70b-versatile` |
| **LLM — fallback** | Azure OpenAI `gpt-4.1-mini` |
| **Embeddings** | Azure OpenAI `text-embedding-3-small` |
| **Web search** | Tavily Search API |
| **Job sources** | Adzuna · Glassdoor · LinkedIn · Wuzzuf · Bayt · Upwork |
| **Vector DB** | Qdrant Cloud (EU-west) |
| **Relational DB** | Supabase Postgres (eu-west-1) |
| **Auth** | Supabase Auth · Google OAuth 2.0 |
| **API** | FastAPI · Uvicorn · SSE streaming |
| **Frontend** | Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui |
| **Tracing** | LangSmith (project: CareerFlow) |
| **CI/CD** | GitHub Actions → Vercel + Hugging Face Spaces |
| **Local dev** | Podman Compose (Postgres + Qdrant) |

## Quickstart (Local)

```bash
# 1. Install deps
uv sync

# 2. Set up environment
cp .env.example .env
# Fill in GROQ_API_KEY, TAVILY_API_KEY, LANGSMITH_API_KEY,
# SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
# QDRANT_URL, QDRANT_API_KEY

# 3. Start infra (Postgres + Qdrant)
podman-compose -f infra/compose.yaml up -d

# 4. Run backend
uv run uvicorn app.main:app --reload
# → http://localhost:8000/health
# → http://localhost:8000/docs

# 5. Run frontend
cd frontend && npm ci && npm run dev
# → http://localhost:3000
```

## Environment Variables

All variables go in `.env` (git-ignored). Copy from `.env.example`.

### Required

| Variable | Source | Description |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Primary LLM |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) | Web search |
| `LANGSMITH_API_KEY` | [smith.langchain.com](https://smith.langchain.com) | Tracing |
| `SUPABASE_URL` | Supabase dashboard | Auth + DB host |
| `SUPABASE_ANON_KEY` | Supabase dashboard | Frontend auth |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard | Backend admin |
| `QDRANT_URL` | [cloud.qdrant.io](https://cloud.qdrant.io) | Vector DB |
| `QDRANT_API_KEY` | Qdrant dashboard | Vector DB auth |

### Optional

| Variable | Description |
|---|---|
| `AZURE_OPENAI_API_KEY` | Fallback LLM + embeddings |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource URL |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Chat model deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` | Embedding model deployment |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna job search |
| `GITHUB_TOKEN` | Portfolio analysis |
| `FRONTEND_URL` | CORS origin (prod: Vercel URL) |

### Frontend (`.env.local`)

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `NEXT_PUBLIC_API_BASE` | `https://AhmedNashat1-career-copilot-api.hf.space` |

## CI/CD Pipeline

```
GitHub push to main
    │
    ├─► CI (ci.yml) ──────────────────────────────────────────────
    │     ├─ Python: ruff lint + pytest (unit + smoke)
    │     ├─ Next.js: vitest + next build
    │     └─ Container: docker buildx (backend + frontend) [main only]
    │
    ├─► Deploy Frontend (deploy-vercel.yml) ──────────────────────
    │     paths: frontend/**
    │     ├─ test-build: npm ci + vitest + next build
    │     ├─ preview:    vercel deploy (PRs → preview URL)
    │     └─ production: vercel deploy --prod → Vercel edge network
    │
    └─► Deploy Backend (deploy-hf.yml) ───────────────────────────
          paths: app/** · pyproject.toml · uv.lock
          ├─ test: ruff + pytest (gates deploy)
          └─ deploy: git-diff → upload changed files → HF Space rebuild
```

### Required GitHub Secrets

| Secret | Where to get it |
|---|---|
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID` | `frontend/.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | `frontend/.vercel/project.json` → `projectId` |
| `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `GH_TOKEN` | GitHub PAT with `repo` scope |

## API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/` | Service info | Public |
| `GET` | `/health` | Health check | Public |
| `GET` | `/docs` | Swagger UI | Public |
| `POST` | `/runs` | Start a copilot run | Required |
| `GET` | `/runs/{id}/stream` | SSE stream of run output | Required |
| `POST` | `/runs/{id}/resume` | Resume after HITL approval | Required |
| `GET` | `/runs/{id}` | Get run state | Required |
| `POST` | `/documents` | Upload CV / documents | Required |
| `GET` | `/matches` | Get job matches | Required |
| `GET` | `/applications` | Get applications | Required |
| `GET` | `/coaching/sessions` | Get coaching sessions | Required |
| `POST` | `/cv/analyze` | Analyze CV | Required |
| `GET` | `/interviews` | Get interview prep | Required |
| `GET` | `/admin/stats` | Admin metrics | Required |

## Database Schema

Run migrations with Alembic:

```bash
uv run alembic upgrade head
```

Or apply the schema directly:

```bash
psql $DATABASE_URL < supabase-schema.sql
```

Tables: `users` · `sessions` · `runs` · `documents` · `job_matches` · `applications` · `coaching_sessions` · `interviews` · `long_term_memory`

## Repository Layout

```
app/
  agents/         cv_analysis · market_research · coaching · matching
                  portfolio · career_planning · application · rag
  api/            FastAPI routers (runs · documents · matches · cv …)
  core/           config · qdrant client · tracing
  db/             Alembic env + migrations
  llm/            multi-provider router (Groq/Azure, reason/fast)
  memory/         Postgres checkpointer + long-term Store
  models/         SQLAlchemy models
  orchestrator/   Supervisor · router · Critic · HITL · CopilotState
  rag/            chunking · fastembed embeddings · Qdrant store
  services/       Supabase client · session management
  tools/          JobSource adapters (Adzuna · Glassdoor · LinkedIn …)
frontend/
  app/            Next.js App Router pages (login · copilot · matches …)
  components/     ChatStream · ApprovalModal · UploadDropzone …
  lib/            API client · Supabase client · useSSE hook · types
backend/
  Containerfile   Production Docker image (python:3.12-slim + uv)
infra/
  compose.yaml    Podman Compose (Postgres + Qdrant + backend + frontend)
.github/workflows/
  ci.yml          Lint · test · container build
  deploy-vercel.yml  Frontend → Vercel
  deploy-hf.yml      Backend → Hugging Face Spaces
docs/
  specs/          Design spec (AI Career Copilot)
  plans/          4 implementation plans (foundation → release)
```

## Local Development Tips

```bash
# Run only backend tests (fast)
uv run pytest tests/ -q --ignore=tests/integration

# Run with real infra (integration tests)
INFRA_UP=1 uv run pytest tests/integration/ -v

# Lint + auto-fix
uv run ruff check . --fix

# Type check (if mypy is installed)
uv run mypy app/

# Frontend type check
cd frontend && npx tsc --noEmit

# Demo end-to-end (requires stack up + .env filled)
bash scripts/demo.sh
```

## Phases Completed

| Phase | Scope | Status |
|---|---|---|
| 1 — Foundation | Monorepo · config · LLM router · embeddings · Postgres + Qdrant · 3 agents ported · LangSmith | ✅ Done |
| 2 — Orchestration | `CopilotState` · Supervisor · RAG pipeline · Critic loop · durable HITL | ✅ Done |
| 3 — Agents & API | Matching · Portfolio · Career Planning · Application agents · JobSource adapters · Alembic · SSE | ✅ Done |
| 4 — Frontend & Release | Next.js dashboard · ApprovalModal · long-term memory · CI/CD · Podman Compose | ✅ Done |

## License

See repository owner. Agents originally authored across `Ahmed-Aboalasaad/career-agent` feature branches.
