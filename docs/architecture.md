# Architecture — AI Career Copilot

## Layered System Diagram

```
┌─────────────────────────────────────────────────────┐
│                   Browser / User                    │
│           Next.js Dashboard  :3000                  │
│  Pages: dashboard · matches · coaching · applications│
│         onboarding · copilot chat                   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│              FastAPI  :8000                         │
│  /health  /documents  /runs  /runs/{id}/resume      │
│  /applications  /coaching                           │
└──────────────────────┬──────────────────────────────┘
                       │ LangGraph invoke / stream
┌──────────────────────▼──────────────────────────────┐
│           Supervisor (LangGraph graph)               │
│  intent → router → plan → fan-out → aggregate       │
│                 │                                   │
│   ┌─────────────┼──────────────────────┐            │
│   │             │                      │            │
│  CV           RAG              Market Research      │
│  Analysis     Knowledge        (Tavily + JobSource) │
│   │             │                      │            │
│  Matching   Coaching           Portfolio/GitHub      │
│   │             │                      │            │
│  Career Planning          Application (generate)    │
│                                        │            │
│                              HITL interrupt/resume  │
│                          Critic (hallucination gate)│
└──────┬──────────────────────────┬──────────────────┘
       │                          │
┌──────▼──────┐           ┌───────▼──────┐
│  Postgres   │           │   Qdrant     │
│  :5432      │           │   :6333      │
│  - runs     │           │  per-user    │
│  - messages │           │  embeddings  │
│  - LangGraph│           │  (RAG)       │
│  checkpoint │           └──────────────┘
└─────────────┘
```

## Agent Roster

| # | Agent | Role | Key Tools |
|---|-------|------|-----------|
| – | Supervisor | Plan, route, aggregate | LangGraph, Postgres checkpointer |
| 1 | CV Analysis | Parse resume, ATS score, skill extract | PyMuPDF, pdfplumber, docx |
| 2 | RAG / Knowledge | Per-user doc ingestion + grounded Q&A | fastembed BGE, Qdrant |
| 3 | Market Research | Job postings, salaries, skill gaps | Tavily, Adzuna/LinkedIn adapters |
| 4 | Job Matching | Semantic rank resume ↔ jobs | Qdrant similarity, LLM re-rank |
| 5 | Coaching | Interview prep, mock Q&A, advice | LLM (reason), session memory |
| 6 | Portfolio/GitHub | Repo analysis, portfolio gaps | GitHub API |
| 7 | Career Planning | 30/60/90-day roadmap synthesis | LLM over upstream outputs |
| 8 | Application | Tailor CV + cover letter + HITL gate | LLM, `interrupt()` / `resume()` |
| – | Critic | Hallucination / grounding check | LLM (reason), evidence[] |

## Data Flow

1. **User uploads resume** → `POST /documents` → stored in Postgres, bytes cached.
2. **User sends query** → `POST /runs` → Supervisor detects intent, builds a `plan`.
3. **Fan-out:** agents run sequentially or in parallel; each writes to its namespaced key in `CopilotState`.
4. **Critic gate:** checks `evidence[]` for grounding; loops up to `MAX_CRITIC_RETRIES = 2` if hallucinated; escalates to HITL on persistent failure.
5. **HITL interrupt:** Application agent calls `interrupt(draft)` before any send; frontend polls SSE stream; user approves via `POST /runs/{id}/resume`.
6. **Response:** Supervisor aggregates; FastAPI streams final answer back to the browser.

## HITL Flow

```
Application agent
  └─ LLM generates draft CV / cover letter
       └─ interrupt(draft)  ← LangGraph pause
            └─ SSE event → frontend shows approval modal
                 └─ User clicks Approve / Edit + Approve
                      └─ POST /runs/{id}/resume  →  graph resumes
                           └─ ApplicationPackage status: APPROVED → SENT
```

## Free LLM Stack

| Task type | Model | Provider |
|-----------|-------|----------|
| `reason` (judgment, synthesis) | Llama 3.3 70B | Groq (free tier) |
| `fast` (routing, extraction) | Llama 3.1 8B | Groq (free tier) |
| Fallback | Gemini 1.5 Flash | Google AI (free tier) |
| Embeddings | BGE-small-en-v1.5 | fastembed (local, keyless) |

## Infrastructure

All services run under Podman via `infra/compose.yaml`:

| Service | Image | Port |
|---------|-------|------|
| postgres | postgres:16 | 5433→5432 |
| qdrant | qdrant/qdrant:latest | 6333→6333 |
| backend | career-copilot-backend (Containerfile) | 8000→8000 |
| frontend | career-copilot-frontend (frontend/Containerfile) | 3000→3000 |

The backend connects to Postgres and Qdrant over the compose internal network.  
The frontend's `NEXT_PUBLIC_API_BASE` is set to `http://localhost:8000` (host-reachable) because the browser runs outside the compose network.
