# AGENTS.md — Agent Behavior Documentation

This document describes the multi-agent behavior of AI Career Copilot (the "Deep Agents" subagent layer). The **Supervisor** plans and routes; each **specialist** is a LangGraph subgraph exposing a node-shaped contract `name_node(state: CopilotState) -> {"name": <output>}` and writing only to its own namespaced state key. A **Critic** validates grounding before any result is surfaced, and a **human approves** every irreversible action.

All agents are **implemented and integrated** as of Plan 4 completion.

## Supervisor (orchestrator)
- **Role:** intent detection, planning, routing (sequential or parallel fan-out), result aggregation, memory + HITL coordination, retry budget.
- **In:** `user_message`, session context, `plan` (from intent router). **Out:** an ordered `plan` of agents to run; the final aggregated answer.
- **Source:** `app/orchestrator/supervisor.py`

## 1. CV Analysis ✅
- **Role:** parse resume (PyMuPDF/pdfplumber/docx), ATS score, extract skills/experience, strengths/weaknesses.
- **In:** `resume_file_bytes` / `resume_text` (+ optional `job_description`). **Out:** `cv_analysis: CVAnalysisResponse`.
- **Tools:** PyMuPDF, pdfplumber, python-docx, LLM extraction.
- **Source:** `app/agents/cv_analysis/`

## 2. RAG / Knowledge ✅
- **Role:** own the per-user knowledge base; ingest uploaded docs → Qdrant; ground answers with citations.
- **In:** `user_message`, `uploaded_doc_ids`. **Out:** `rag: {answer, citations}` + `evidence[]`.
- **Tools:** fastembed BGE embeddings, Qdrant vector store, LLM synthesis.
- **Source:** `app/agents/rag/`

## 3. Market / Job Research ✅
- **Role:** web + job-board research (postings, salaries, trends, skill gap) via the `JobSource` adapters + Tavily.
- **In:** `market_input`. **Out:** `market: MarketAgentOutput`.
- **Tools:** Tavily web search, Adzuna/LinkedIn/Glassdoor `JobSource` adapters.
- **Source:** `app/agents/market_research/`

## 4. Job Matching ✅
- **Role:** semantic match resume ↔ jobs, rank top-N with rationale. **Out:** `matching: {ranked[]}`.
- **Tools:** Qdrant vector similarity, LLM re-ranking.
- **Source:** `app/agents/matching/`

## 5. Coaching ✅
- **Role:** interview prep, mock Q&A, feedback, career advice. **Out:** `coaching: ChatResponse`.
- **Tools:** LLM (reason task), session memory.
- **Source:** `app/agents/coaching/`

## 6. Portfolio / GitHub ✅
- **Role:** analyze GitHub repos/languages/activity; portfolio strengths/gaps/suggestions. **Out:** `portfolio: PortfolioReport`.
- **Tools:** GitHub API (`GITHUB_TOKEN`), LLM analysis.
- **Source:** `app/agents/portfolio/`

## 7. Career Planning ✅
- **Role:** synthesize CV + skill gap + market + portfolio into a target role + 30/60/90-day roadmap. **Out:** `career_plan: CareerPlan`.
- **Tools:** LLM synthesis over upstream agent outputs.
- **Source:** `app/agents/career_planning/`

## 8. Application (generate + HITL) ✅
- **Role:** tailor CV, write cover letter (≤400 words) + application email; prepare submission. **Never auto-submits.**
- **HITL:** emits an `interrupt()` with the draft; a human approves/edits before any send. **Out:** `application: ApplicationPackage` (`DRAFT` → `APPROVED` / `SENT`).
- **Tools:** LLM generation, Postgres durable state, `interrupt()` / `resume()` LangGraph primitives.
- **Source:** `app/agents/application/`

## Critic / Judge ✅
- **Role:** grounding/hallucination check against `evidence`; "loop if hallucinated" with `MAX_CRITIC_RETRIES = 2`, else escalate to HITL. **Out:** `critic_verdict: {grounded, issues, action}`.
- **Tools:** LLM (reason task), `evidence[]` from RAG.
- **Source:** `app/orchestrator/critic.py`

## HITL Gate ✅
- **Role:** interrupt/resume gate wrapping any irreversible action (application send, large profile writes). Surfaces a pending approval to the frontend via SSE; resumes on `POST /runs/{run_id}/resume`.
- **Source:** `app/orchestrator/hitl.py`, `app/api/runs.py`

## Cross-cutting conventions
- **State:** one shared `CopilotState` (`app/orchestrator/state.py`); accumulators (`messages`, `evidence`, `errors`) use reducers; agent outputs are overwrite-safe namespaced keys.
- **LLM:** only via `app.llm.provider.get_llm(task, temperature, max_tokens)` — `reason` (Llama 3.3 70B) for judgment, `fast` (Llama 3.1 8B) for routing/extraction; Gemini fallback.
- **Durability:** Postgres checkpointer makes runs resumable and lets HITL interrupts survive restarts.
- **Tracing:** LangSmith wraps every node.
- **Router:** `app/orchestrator/router.py` resolves user intent to an agent sequence.
