# AGENTS.md — Agent Behavior Documentation

This document describes the multi-agent behavior of AI Career Copilot (the "Deep Agents" subagent layer). The **Supervisor** plans and routes; each **specialist** is a LangGraph subgraph exposing a node-shaped contract `name_node(state: CopilotState) -> {"name": <output>}` and writing only to its own namespaced state key. A **Critic** validates grounding before any result is surfaced, and a **human approves** every irreversible action.

> Status: the Supervisor, Critic, and HITL gate land in Phase 2; agents 4–8 in Phase 3 (see `docs/plans/`). Phase 1 ships agents 1–3 as compiled subgraphs.

## Supervisor (orchestrator)
- **Role:** intent detection, planning, routing (sequential or parallel fan-out), result aggregation, memory + HITL coordination, retry budget.
- **Out:** an ordered `plan` of agents to run; the final aggregated answer.

## 1. CV Analysis  ✅ ported
- **Role:** parse resume (PyMuPDF/pdfplumber/docx), ATS score, extract skills/experience, strengths/weaknesses.
- **In:** `resume_file_bytes`/`resume_text` (+ optional `job_description`). **Out:** `cv_analysis: CVAnalysisResponse`.

## 2. RAG / Knowledge  🚧
- **Role:** own the per-user knowledge base; ingest uploaded docs → Qdrant; ground answers with citations.
- **In:** `user_message`, `uploaded_doc_ids`. **Out:** `rag: {answer, citations}` + `evidence[]`.

## 3. Market / Job Research  ✅ ported
- **Role:** web + job-board research (postings, salaries, trends, skill gap) via the `JobSource` adapters + Tavily.
- **In:** `market_input`. **Out:** `market: MarketAgentOutput`.

## 4. Job Matching  ⬜
- **Role:** semantic match resume ↔ jobs, rank top-N with rationale. **Out:** `matching: {ranked[]}`.

## 5. Coaching  ✅ ported
- **Role:** interview prep, mock Q&A, feedback, career advice. **Out:** `coaching: ChatResponse`.

## 6. Portfolio / GitHub  ⬜
- **Role:** analyze GitHub repos/languages/activity; portfolio strengths/gaps/suggestions. **Out:** `portfolio: PortfolioReport`.

## 7. Career Planning  ⬜
- **Role:** synthesize CV + skill gap + market + portfolio into a target role + 30/60/90 roadmap. **Out:** `career_plan: CareerPlan`.

## 8. Application (generate + HITL)  ⬜
- **Role:** tailor CV, write cover letter (≤400 words) + application email; prepare submission. **Never auto-submits.**
- **HITL:** emits an `interrupt()` with the draft; a human approves/edits before any send. **Out:** `application: ApplicationPackage` (`DRAFT`→`APPROVED`/`SENT`).

## Critic / Judge  ⬜
- **Role:** grounding/hallucination check against `evidence`; "loop if hallucinated" with `MAX_CRITIC_RETRIES = 2`, else escalate to HITL. **Out:** `critic_verdict: {grounded, issues, action}`.

## Cross-cutting conventions
- **State:** one shared `CopilotState`; accumulators (`messages`, `evidence`, `errors`) use reducers; agent outputs are overwrite-safe namespaced keys.
- **LLM:** only via `app.llm.provider.get_llm(task, temperature, max_tokens)` — `reason` (Llama 3.3 70B) for judgment, `fast` (Llama 3.1 8B) for routing/extraction; Gemini fallback.
- **Durability:** Postgres checkpointer makes runs resumable and lets HITL interrupts survive restarts.
- **Tracing:** LangSmith wraps every node.
