# AI Career Copilot

[![CI](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/ci.yml)
[![Deploy Frontend](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-vercel.yml/badge.svg)](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-vercel.yml)
[![Deploy Backend](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-hf.yml/badge.svg)](https://github.com/ahmednashatnoaman-svg/career-copilot/actions/workflows/deploy-hf.yml)

An end-to-end **multi-agent career assistant** powered by LangGraph, Groq LLaMA-3, and Qdrant. It analyzes your CV, researches live job opportunities, matches and ranks roles, coaches you through interviews, and generates tailored application materials — with a **human-in-the-loop approval gate** before any irreversible action.

---

## Live Deployment

| Service | URL |
|---|---|
| **Frontend** (Vercel) | https://career-copilot-fawn.vercel.app |
| **Backend API** (HF Spaces) | https://AhmedNashat1-career-copilot-api.hf.space |
| **API Docs** (Swagger) | https://AhmedNashat1-career-copilot-api.hf.space/docs |
| **HF Space** | https://huggingface.co/spaces/AhmedNashat1/career-copilot-api |
| **Tracing** (LangSmith) | https://smith.langchain.com → project *CareerFlow* |

---

## What It Does

1. **CV Analysis** — Extracts skills, experience, and gaps using RAG over your uploaded documents (PDF/DOCX/PNG with OCR).
2. **Market Research** — Live job search via Tavily, Adzuna, LinkedIn, Glassdoor, Wuzzuf, and Bayt.
3. **Job Matching** — Cosine-similarity ranking over Qdrant vectors; returns scored, annotated matches.
4. **Career Coaching** — Conversational coach with long-term memory (Postgres) and `NullMemory` graceful fallback when the DB is unreachable.
5. **Interview Prep** — Adaptive mock interviews: tracks per-session Q&A, scores answers, generates feedback.
6. **Portfolio Analysis** — GitHub API integration: activity stats, language breakdown, project highlights.
7. **Career Planning** — Structured roadmap generation with skill-gap milestones.
8. **Application Writer** — Tailored cover letter + CV edits, gated by a Critic loop (halts on hallucinations) and HITL approval.

---

## Architecture

```
Browser (Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui)
    │  Supabase Google OAuth  ·  JWT on every API request
    ▼
FastAPI (Hugging Face Spaces · Docker · port 7860)
    │  JWTAuthMiddleware → verify Supabase JWT
    │  Routers: /runs  /documents  /matches  /coaching  /cv  /interviews
    ▼
Supervisor (LangGraph StateGraph · CopilotState)
    ├─ CV Analysis Agent        ← fastembed chunks → Qdrant RAG
    ├─ Market Research Agent    ← Tavily · Adzuna · Glassdoor · LinkedIn
    ├─ Job Matching Agent       ← cosine similarity over Qdrant vectors
    ├─ Career Coaching Agent    ← LangGraph sub-graph · Postgres memory
    │       NullMemory fallback ← no-op when Postgres is unreachable
    ├─ Interview Prep Agent     ← context-aware adaptive Q&A
    ├─ Portfolio Analyzer       ← GitHub REST API
    ├─ Career Planning Agent    ← structured roadmap generation
    └─ Application Writer       ← cover letter + CV tailoring
           │  Critic loop (stops if hallucinated content detected)
           │  HITL interrupt → frontend ApprovalModal → graph.resume()
           ▼
    Postgres (Supabase)   — LangGraph checkpointer + coaching long-term store
    Qdrant Cloud          — per-user document vectors (collection: career_docs)
    LangSmith             — full trace on every run (project: CareerFlow)
```

### Request Flow

```
POST /runs  →  Supervisor.invoke()  →  SSE stream via GET /runs/{id}/stream
                                         ↑ Authorization: Bearer <supabase-jwt>
                                         ↑ useSSE hook (frontend/lib/useSSE.ts)

HITL gate:  graph raises NodeInterrupt  →  run status = "awaiting_approval"
            POST /runs/{id}/resume      →  graph.update_state() + resume()
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph 0.2 (supervisor graph, HITL interrupt/resume, sub-graphs) |
| **LLM — primary** | Groq `llama-3.3-70b-versatile` |
| **LLM — fast/cheap** | Groq `llama-3.1-8b-instant` |
| **Embeddings** | fastembed (local) |
| **Web search** | Tavily Search API |
| **Job sources** | Adzuna · Glassdoor · LinkedIn · Wuzzuf · Bayt · Upwork |
| **Vector DB** | Qdrant Cloud |
| **Relational DB** | Supabase Postgres (EU-west-1) |
| **Auth** | Supabase Auth · Google OAuth 2.0 |
| **Document parsing** | PyMuPDF · pytesseract (OCR) · pdf2image · python-docx |
| **API** | FastAPI · Uvicorn[standard] · SSE streaming |
| **Frontend** | Next.js 15 (App Router) · TypeScript · Tailwind CSS · shadcn/ui |
| **Tracing** | LangSmith (project: CareerFlow) |
| **CI/CD** | GitHub Actions → Vercel (frontend) + Hugging Face Spaces Docker (backend) |
| **Containers** | Docker / Podman · `python:3.12-slim` + `uv` |
| **Package manager** | `uv` (Python) · `npm` (frontend) |
| **Local dev** | Podman Compose (Postgres + Qdrant) |

---

## Quickstart (Local)

### Prerequisites

- Python 3.12+ · [`uv`](https://docs.astral.sh/uv/) · Node.js 20+ · Podman or Docker

### Backend

```bash
# Clone and install
git clone https://github.com/ahmednashatnoaman-svg/career-copilot
cd career-copilot
uv sync

# Configure environment
cp .env.example .env
# Fill in all required variables (see table below)

# Start infra (Postgres + Qdrant)
podman-compose -f infra/compose.yaml up -d

# Run backend
uv run uvicorn app.main:app --reload --port 8000
# Swagger UI → http://localhost:8000/docs
# Health     → http://localhost:8000/health
```

### Frontend

```bash
cd frontend
npm ci

# Create .env.local
echo "NEXT_PUBLIC_SUPABASE_URL=https://<your-project>.supabase.co" >> .env.local
echo "NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>" >> .env.local
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" >> .env.local

npm run dev
# → http://localhost:3000
```

---

## Environment Variables

### Backend (`.env`)

#### Required

| Variable | Source | Description |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Primary LLM |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) | Web search |
| `LANGSMITH_API_KEY` | [smith.langchain.com](https://smith.langchain.com) | Tracing |
| `SUPABASE_URL` | Supabase dashboard → Settings → API | Auth + DB host |
| `SUPABASE_ANON_KEY` | Supabase dashboard | Frontend auth (safe to expose) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard | Backend admin — bypasses RLS |
| `QDRANT_URL` | [cloud.qdrant.io](https://cloud.qdrant.io) | Vector DB cluster URL |
| `QDRANT_API_KEY` | Qdrant dashboard | Vector DB auth |
| `FRONTEND_URL` | Your Vercel domain | CORS allow-origin — **no trailing slash** |

#### Optional

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres DSN — enables LangGraph checkpointer + coaching memory |

| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna job search |
| `GITHUB_TOKEN` | Portfolio analysis via GitHub REST API |
| `LLM_PROVIDER` | `groq` (default) or `google` |
| `LLM_MODEL` | Override primary model name |
| `LLM_MODEL_FAST` | Override fast model name |

> **Security**: All secrets go in `.env` (git-ignored). Never commit keys.

### Frontend (`.env.local`)

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `NEXT_PUBLIC_API_BASE` | Backend URL (`https://AhmedNashat1-career-copilot-api.hf.space` in prod) |

### HF Space Variables (set in Space Settings → Variables)

| Variable | Notes |
|---|---|
| `GROQ_API_KEY` | Required |
| `TAVILY_API_KEY` | Required |
| `SUPABASE_URL` | Required |
| `SUPABASE_SERVICE_ROLE_KEY` | Required |
| `QDRANT_URL` | Required |
| `QDRANT_API_KEY` | Required |
| `FRONTEND_URL` | `https://career-copilot-fawn.vercel.app` — no trailing slash |
| `DATABASE_URL` | Optional — coaching memory disabled (NullMemory) when absent |

---

## API Reference

All protected endpoints require `Authorization: Bearer <supabase-jwt>` header.

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | Public | Service info |
| `GET` | `/health` | Public | Health check |
| `GET` | `/docs` | Public | Swagger UI |
| `POST` | `/runs` | Required | Start a copilot run |
| `GET` | `/runs/{id}/stream` | Required | SSE stream of run output |
| `POST` | `/runs/{id}/resume` | Required | Resume after HITL approval |
| `GET` | `/runs/{id}` | Required | Get run state |
| `POST` | `/documents` | Required | Upload CV / supporting documents |
| `GET` | `/matches` | Required | Get ranked job matches |
| `GET` | `/applications` | Required | Get application history |
| `POST` | `/coaching/chat` | Required | Chat with career coaching agent |
| `POST` | `/cv/analyze` | Required | Analyze CV and extract insights |
| `GET` | `/interviews` | Required | Get interview prep sessions |
| `GET` | `/admin/stats` | Required | Admin metrics dashboard |

### SSE Stream Events

```
data: {"type": "thinking", "content": "…"}
data: {"type": "agent_output", "agent": "cv_analysis", "content": "…"}
data: {"type": "hitl_interrupt", "action": "apply_to_job", "payload": {…}}
data: {"type": "done", "run_id": "…"}
```

---

## CI/CD Pipeline

```
git push → main
    │
    ├─► ci.yml ─────────────────────────────────────────────────────────
    │     ├─ Python: ruff lint + pytest (unit + smoke)
    │     ├─ Next.js: vitest + next build
    │     └─ Container: docker buildx (smoke test only)
    │
    ├─► deploy-vercel.yml ──────────────────────────────────────────────
    │     trigger: frontend/**
    │     ├─ test-build: npm ci + vitest + next build
    │     └─ production: vercel --prod → Vercel edge network
    │
    └─► deploy-hf.yml ──────────────────────────────────────────────────
          trigger: app/** · pyproject.toml · uv.lock · Dockerfile
          ├─ test: ruff lint + pytest (gates deploy)
          └─ deploy: git-diff → upload changed files → HF Space rebuild
                     Dockerfile · pyproject.toml · uv.lock always synced
```

Supports `workflow_dispatch` for manual re-deploys from GitHub Actions UI.

### Required GitHub Secrets

| Secret | Where to get it |
|---|---|
| `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — write access |
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID` | `frontend/.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | `frontend/.vercel/project.json` → `projectId` |

---

## HuggingFace Space Setup

The backend is deployed as a **Docker Space** on HuggingFace Spaces. On every push the GitHub Action uploads changed `app/` files plus `Dockerfile`, `pyproject.toml`, and `uv.lock` — HF Spaces rebuilds the container automatically.

### Space Environment Variables

Set the variables listed in the [HF Space Variables](#hf-space-variables-set-in-space-settings--variables) table above via:
**Space → Settings → Variables and secrets → New variable**

### Container Details

```dockerfile
FROM python:3.12-slim
# System deps: tesseract-ocr, poppler-utils, libgomp1
# Package manager: uv (fast, lock-file-based)
# Port: 7860 (HF Space default)
# Command: uvicorn app.main:app --host 0.0.0.0 --port 7860
```

---

## Database

### Supabase Tables (application data — RLS enabled)

| Table | Description |
|---|---|
| `users` | User profiles, preferences |
| `sessions` | Active copilot sessions |
| `runs` | Agent run history + state |
| `documents` | Uploaded CV/document metadata |
| `job_matches` | Scored job match results |
| `applications` | Application tracking |
| `coaching_sessions` | Coaching thread metadata |
| `interviews` | Interview session records |

### Coaching Memory Tables (Postgres — optional)

When `DATABASE_URL` is set and reachable, the coaching agent uses `PostgresMemory`:

| Table | Description |
|---|---|
| `conversations` | Per-thread message history |
| `interview_sessions` | Adaptive interview state |
| `interview_turns` | Per-question Q&A + scores |
| `career_plans` | Generated roadmaps |
| `memory_items` | Vector-indexed long-term facts |

When `DATABASE_URL` is absent or the connection fails, `NullMemory` activates automatically — all coaching features work without persistence.

### Apply Schema

```bash
# Via Supabase dashboard SQL Editor
psql $DATABASE_URL < supabase-schema.sql

# Via Alembic migrations
uv run alembic upgrade head
```

---

## Repository Layout

```
career-copilot/
├── Dockerfile                    # HF Space Docker build (port 7860)
├── pyproject.toml                # Python deps + uv config
├── uv.lock                       # Locked dependency tree
├── ruff.toml                     # Linter config
├── alembic.ini                   # Alembic migration config
│
├── app/                          # FastAPI application
│   ├── main.py                   # App factory · middleware · routers
│   ├── core/
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   ├── clients.py            # Qdrant + Supabase singletons
│   │   └── tracing.py            # LangSmith setup
│   ├── api/                      # FastAPI routers
│   │   ├── runs.py               # Copilot run lifecycle + SSE
│   │   ├── coaching.py           # Coaching chat endpoint
│   │   ├── documents.py          # Document upload + ingest
│   │   ├── matches.py            # Job match retrieval
│   │   ├── cv.py                 # CV analysis
│   │   ├── interviews.py         # Interview prep
│   │   ├── applications.py       # Application tracking
│   │   └── admin.py              # Admin stats
│   ├── orchestrator/
│   │   ├── supervisor.py         # LangGraph supervisor StateGraph
│   │   └── hitl.py               # Human-in-the-loop interrupt/resume
│   ├── agents/                   # Per-domain agent sub-graphs
│   │   ├── coaching/
│   │   │   ├── graph.py          # Coaching sub-graph (NullMemory fallback)
│   │   │   ├── memory.py         # PostgresMemory + NullMemory
│   │   │   └── agent.py          # CareerCoachingAgent
│   │   ├── cv_analysis/
│   │   ├── market_research/
│   │   ├── matching/
│   │   ├── portfolio/
│   │   ├── career_planning/
│   │   ├── application/
│   │   └── rag/
│   ├── rag/
│   │   ├── ingest.py             # PDF/DOCX/image → chunks → Qdrant
│   │   ├── chunking.py           # Token-aware text splitter
│   │   ├── retriever.py          # Qdrant semantic search
│   │   ├── embeddings.py         # fastembed
│   │   └── store.py              # Qdrant collection management
│   ├── memory/
│   │   ├── checkpointer.py       # LangGraph Postgres checkpointer
│   │   └── longterm.py           # Long-term memory store
│   ├── llm/
│   │   └── provider.py           # Multi-provider LLM router (Groq / Google)
│   ├── services/
│   │   ├── supabase_db.py        # Supabase data operations
│   │   └── session.py            # Session management
│   ├── tools/                    # JobSource adapters
│   └── models/
│       └── db.py                 # SQLAlchemy models
│
├── frontend/                     # Next.js 15 App Router
│   ├── app/
│   │   ├── page.tsx              # Landing page
│   │   ├── login/ signup/        # Auth flows
│   │   ├── copilot/              # Main chat + run interface
│   │   ├── matches/              # Job match dashboard
│   │   ├── coaching/             # Coaching interface
│   │   ├── interviews/           # Interview prep
│   │   └── applications/         # Application tracker
│   ├── components/               # Shared UI components
│   │   ├── ChatStream.tsx        # SSE-driven chat stream
│   │   ├── ApprovalModal.tsx     # HITL approval UI
│   │   └── UploadDropzone.tsx    # Document upload
│   └── lib/
│       ├── useSSE.ts             # SSE hook with auth headers
│       ├── api.ts                # Typed API client
│       └── supabase.ts           # Supabase client
│
├── tests/                        # pytest test suite
├── infra/
│   └── compose.yaml              # Podman Compose (Postgres + Qdrant)
├── backend/
│   └── Containerfile             # Local dev container (port 8000)
├── docs/
│   ├── specs/                    # Design specifications
│   └── plans/                    # Implementation plans (4 phases)
└── .github/workflows/
    ├── ci.yml                    # Lint · test · container smoke
    ├── deploy-vercel.yml         # Frontend → Vercel
    └── deploy-hf.yml             # Backend → HF Space (Docker rebuild)
```

---

## Development

```bash
# Run backend tests only
uv run pytest tests/ -q --ignore=tests/integration

# Run with real infra
INFRA_UP=1 uv run pytest tests/integration/ -v

# Lint + auto-fix
uv run ruff check . --fix

# Type check
uv run mypy app/

# Frontend type check
cd frontend && npx tsc --noEmit

# Frontend unit tests
cd frontend && npm run test

# Manually trigger HF Space re-deploy
gh workflow run deploy-hf.yml --repo ahmednashatnoaman-svg/career-copilot
```

---

## Deployment Status

| Phase | Scope | Status |
|---|---|---|
| 1 — Foundation | Monorepo · config · LLM router · embeddings · Postgres + Qdrant · base agents · LangSmith | ✅ Done |
| 2 — Orchestration | `CopilotState` · Supervisor · RAG pipeline · Critic loop · durable HITL | ✅ Done |
| 3 — Agents & API | Matching · Portfolio · Career Planning · Application agents · JobSource adapters · Alembic · SSE | ✅ Done |
| 4 — Frontend & Release | Next.js dashboard · ApprovalModal · Coaching memory · CI/CD · Docker HF Space | ✅ Done |

---

## License

See repository owner. Core agents authored by the CareerFlow team.
