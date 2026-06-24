# Orchestration, RAG, Critic & HITL — Implementation Plan (Plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. Follows Plan 1's TDD micro-step discipline (RED → GREEN → commit).

**Goal:** Add the Supervisor that plans/routes to the ported agents, a RAG pipeline over uploaded documents, a Critic ("loop if hallucinated") gate, and a durable Human-in-the-Loop interrupt before irreversible actions — all on the Postgres checkpointer.

**Architecture:** One `CopilotState` typed dict flows through a Supervisor `StateGraph`. The Supervisor routes (sequential or `Send` fan-out) to specialist subgraphs from Plan 1, a RAG agent grounds answers from Qdrant, a Critic node validates grounding and loops back with a bounded retry budget, and `interrupt()` pauses before application-send. Runs are checkpointed in Postgres so an interrupt survives a restart and resumes via `Command(resume=...)`.

**Tech Stack:** LangGraph 1.2.6 (StateGraph, `Send`, `interrupt`, `Command`, `PostgresSaver`, `PostgresStore`), fastembed (`bge-small-en-v1.5`), Qdrant, Groq/Gemini via `app.llm.provider`.

**Depends on:** Plan 1 (config, `get_llm`, embeddings, checkpointer/store factories, ported agents `market_research`/`cv_analysis`/`coaching`, Qdrant client, Postgres+Qdrant via Podman).

## Global Constraints

- All Plan 1 Global Constraints still bind (Python ≥3.12, package root `app/`, free providers only, LLM via `get_llm`, embeddings via `get_embedder`, config via `get_settings`, Conventional Commits).
- The shared graph state is `app.orchestrator.state.CopilotState`. Specialist outputs live under **namespaced keys** (`cv_analysis`, `market`, `coaching`, `rag`, …) so parallel branches never collide — same convention the CV agent's `graph_node.py` already uses.
- Parallel branches accumulate via reducers (`Annotated[list, add]` / dict-merge). Never overwrite a sibling branch's key.
- HITL uses LangGraph `interrupt()` + `Command(resume=...)` (the 1.x idiom), NOT `interrupt_before`+`update_state`. The graph MUST be compiled with the Postgres checkpointer for interrupts to persist.
- The Critic retry budget is `MAX_CRITIC_RETRIES = 2`; after that it escalates to HITL, never loops unbounded.
- Embeddings dimension is `EMBED_DIM = 384`; Qdrant collections use `Distance.COSINE`. Per-user isolation via a `user_id` payload filter on every query.
- Branch: continue on `feat/foundation-monorepo` (or a `feat/orchestration` branch off it).

---

## File structure produced by this plan

```
app/orchestrator/
  __init__.py
  state.py            # CopilotState + reducers + sub-models
  router.py           # intent detection + routing decision (structured output)
  supervisor.py       # the Supervisor StateGraph (build_supervisor(checkpointer))
  critic.py           # critic_node + grounding check + loop control
  hitl.py             # interrupt helpers + resume payloads
app/rag/
  chunking.py         # document → chunks
  ingest.py           # parse → chunk → embed → Qdrant upsert
  store.py            # Qdrant collection mgmt + upsert/query
  retriever.py        # semantic retrieval (user-filtered)
app/agents/rag/
  __init__.py
  agent.py            # rag_node(state) -> {"rag": RagResult}
tests/
  test_state.py  test_chunking.py  test_rag_store.py  test_retriever.py
  test_router.py  test_critic.py  test_hitl.py
  integration/test_supervisor_e2e.py   # INFRA_UP=1
```

---

### Task 1: Shared graph state (`app/orchestrator/state.py`)

**Files:** Create `app/orchestrator/__init__.py`, `app/orchestrator/state.py`, `tests/test_state.py`.

**Interfaces — Produces:**
```python
class HitlRequest(BaseModel):
    kind: Literal["application_send", "critic_escalation", "shortlist_approval"]
    payload: dict
    prompt: str

class CopilotState(TypedDict, total=False):
    # inputs
    user_id: str
    thread_id: str
    user_message: str
    uploaded_doc_ids: list[str]
    # routing
    plan: list[str]                      # ordered agent names to run
    next_agent: str | None
    # namespaced agent outputs (overwrite-safe, one key per agent)
    cv_analysis: dict
    market: dict
    rag: dict
    coaching: dict
    matching: dict
    portfolio: dict
    career_plan: dict
    application: dict
    # accumulators
    messages: Annotated[list, add_messages]
    evidence: Annotated[list[dict], add]     # retrieved chunks/citations
    errors: Annotated[list[str], add]
    # control
    critic_verdict: dict | None
    critic_retries: int
    hitl_request: HitlRequest | None
    final_answer: str | None
```

- [ ] **Step 1 (RED):** `tests/test_state.py` — assert `CopilotState` annotations include the namespaced keys and that `add_messages`/`add` reducers are attached to `messages`/`evidence`/`errors` (`typing.get_type_hints(..., include_extras=True)` then check `Annotated` metadata). Run `uv run pytest tests/test_state.py -v` → FAIL.
- [ ] **Step 2 (GREEN):** Implement `state.py` exactly as the interface block above (import `add_messages` from `langgraph.graph.message`, `add` from `operator`). Re-run → PASS.
- [ ] **Step 3:** `uv run ruff check .`; commit `feat: shared CopilotState with namespaced agent keys and reducers`.

---

### Task 2: Document chunking (`app/rag/chunking.py`)

**Files:** Create `app/rag/chunking.py`, `tests/test_chunking.py`.

**Interfaces — Produces:** `chunk_text(text: str, *, target_tokens: int = 600, overlap: int = 80) -> list[str]` (recursive split on paragraph→sentence boundaries; never returns empty for non-empty input; chunks ≤ target with overlap).

- [ ] **Step 1 (RED):** test that a 3000-word string yields >1 chunk, each non-empty, consecutive chunks share overlap text, and a 5-word string yields exactly 1 chunk. → FAIL.
- [ ] **Step 2 (GREEN):** Implement with a simple token estimate (`len(text.split())` proxy or `tiktoken`); split on `\n\n`, then pack to target with overlap. → PASS.
- [ ] **Step 3:** ruff; commit `feat: recursive document chunking for RAG`.

---

### Task 3: Qdrant collection + upsert/query (`app/rag/store.py`)

**Files:** Create `app/rag/store.py`, `tests/test_rag_store.py` (unit, mocked client) + add to `tests/integration/test_infra.py` (live).

**Interfaces — Produces:**
```python
COLLECTION = "career_docs"
def ensure_collection() -> None                      # create if missing, size=EMBED_DIM, COSINE
def upsert_chunks(user_id: str, doc_id: str, chunks: list[str]) -> int   # embeds + upserts, returns count
def query(user_id: str, text: str, top_k: int = 6) -> list[dict]         # [{text, score, doc_id}], user-filtered
```

- [ ] **Step 1 (RED):** unit test with a mocked `QdrantClient` asserting `ensure_collection` calls `create_collection` with `size=384, distance=COSINE` only when absent, and `query` always passes a `must` filter on `user_id`. → FAIL.
- [ ] **Step 2 (GREEN):** Implement using `app.core.clients.get_qdrant`, `app.rag.embeddings.embed_texts`, payload `{user_id, doc_id, text}`, `Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])`. → PASS.
- [ ] **Step 3 (live, INFRA_UP=1):** integration test: `ensure_collection()`, upsert 3 chunks for `user_a` + 3 for `user_b`, assert `query("user_a", ...)` never returns `user_b` payloads. → PASS.
- [ ] **Step 4:** ruff; commit `feat: qdrant store with per-user isolation`.

---

### Task 4: Ingestion pipeline + retriever (`app/rag/ingest.py`, `app/rag/retriever.py`)

**Files:** Create `app/rag/ingest.py`, `app/rag/retriever.py`, `tests/test_retriever.py`.

**Interfaces — Produces:**
- `ingest_document(user_id: str, doc_id: str, *, file_bytes: bytes|None=None, filename: str|None=None, text: str|None=None) -> int` — parse (reuse `app.agents.cv_analysis.core.extraction.parser` for PDF/docx; plain text passthrough) → `chunk_text` → `upsert_chunks`.
- `retrieve(user_id: str, query: str, top_k: int = 6) -> list[dict]` — thin wrapper over `store.query`, returns evidence dicts `{text, score, doc_id, source:"rag"}`.

- [ ] **Step 1 (RED):** `test_retriever.py` monkeypatches `store.query` to return canned hits and asserts `retrieve` shapes them into evidence dicts with `source="rag"`. → FAIL.
- [ ] **Step 2 (GREEN):** Implement both; `ingest_document` dispatches on input type and reuses the CV agent's parser for files. → PASS.
- [ ] **Step 3:** ruff; commit `feat: rag ingestion pipeline and retriever`.

---

### Task 5: RAG agent node (`app/agents/rag/agent.py`)

**Files:** Create `app/agents/rag/__init__.py`, `app/agents/rag/agent.py`, extend `tests/test_agents_smoke.py`.

**Interfaces — Produces:** `rag_node(state: CopilotState) -> dict` returning `{"rag": {"answer": str, "citations": list[dict]}, "evidence": [...]}`. Retrieves with `retrieve(state["user_id"], state["user_message"])`, then calls `get_llm("reason")` with a grounded-answer prompt that MUST cite or say "not found in documents".

- [ ] **Step 1 (RED):** smoke test: monkeypatch `retrieve` to return 2 hits and `get_llm` to a stub; assert `rag_node` returns `rag.answer` non-empty and `evidence` has 2 items. → FAIL.
- [ ] **Step 2 (GREEN):** Implement. → PASS.
- [ ] **Step 3:** ruff; commit `feat: rag knowledge agent node`.

---

### Task 6: Router (`app/orchestrator/router.py`)

**Files:** Create `app/orchestrator/router.py`, `tests/test_router.py`.

**Interfaces — Produces:**
```python
class RoutingDecision(BaseModel):
    plan: list[str]          # subset/order of: ["cv_analysis","rag","market","matching","coaching","application"]
    rationale: str
def route(state: CopilotState) -> dict   # returns {"plan": [...], "next_agent": plan[0]}
```
Uses `get_llm("fast").with_structured_output(RoutingDecision)` over the user message + which doc_ids exist. Deterministic guardrail: if message mentions "apply"/"application" → ensure `application` is last; if docs uploaded and no CV yet → prepend `cv_analysis`.

- [ ] **Step 1 (RED):** test with a stubbed structured LLM returning `["market"]` for "find AI jobs", asserting `route` sets `plan` and `next_agent="market"`; and a guardrail test that "apply to this job" forces `application` last. → FAIL.
- [ ] **Step 2 (GREEN):** Implement with the structured-output call + post-processing guardrails. → PASS.
- [ ] **Step 3:** ruff; commit `feat: supervisor router with structured routing decision`.

---

### Task 7: Critic node + bounded loop (`app/orchestrator/critic.py`)

**Files:** Create `app/orchestrator/critic.py`, `tests/test_critic.py`.

**Interfaces — Produces:**
```python
class CriticVerdict(BaseModel):
    grounded: bool
    issues: list[str]
    action: Literal["ACCEPT","REGENERATE","ESCALATE"]
def critic_node(state: CopilotState) -> dict
def critic_route(state: CopilotState) -> str   # "regenerate" | "escalate" | "accept"
```
`critic_node` asks `get_llm("reason").with_structured_output(CriticVerdict)` to judge the latest draft (`final_answer`/`application`) against `state["evidence"]`. It increments `critic_retries`; if `not grounded` and `critic_retries > MAX_CRITIC_RETRIES` → force `action="ESCALATE"`. `critic_route` maps verdict+budget to the next edge.

- [ ] **Step 1 (RED):** tests: (a) grounded verdict → `critic_route=="accept"`; (b) ungrounded with retries=0 → `"regenerate"` and `critic_retries` incremented; (c) ungrounded with retries already at budget → `"escalate"`. → FAIL.
- [ ] **Step 2 (GREEN):** Implement with `MAX_CRITIC_RETRIES = 2`. → PASS.
- [ ] **Step 3:** ruff; commit `feat: critic node with bounded regenerate-or-escalate loop`.

---

### Task 8: HITL helpers (`app/orchestrator/hitl.py`)

**Files:** Create `app/orchestrator/hitl.py`, `tests/test_hitl.py`.

**Interfaces — Produces:**
- `request_approval(kind, payload, prompt) -> Any` — wraps LangGraph `interrupt({...})`; returns the human's resume value.
- `application_send_node(state) -> dict` — builds a `HitlRequest(kind="application_send", ...)`, calls `request_approval`, and on resume sets `application["status"]` to `APPROVED`/`SENT` or `REJECTED` based on the resume payload.

- [ ] **Step 1 (RED):** test that `application_send_node` calls `interrupt` (monkeypatched to raise a sentinel `GraphInterrupt` or return a canned approval) and, given a resume payload `{"approved": True}`, sets `application.status == "APPROVED"`. → FAIL.
- [ ] **Step 2 (GREEN):** Implement using `from langgraph.types import interrupt`. → PASS.
- [ ] **Step 3:** ruff; commit `feat: HITL interrupt helper and application-send gate`.

---

### Task 9: Supervisor graph + wiring (`app/orchestrator/supervisor.py`)

**Files:** Create `app/orchestrator/supervisor.py`, extend `tests/integration/test_supervisor_e2e.py`.

**Interfaces — Produces:** `build_supervisor(checkpointer=None) -> CompiledGraph`. Nodes: `router`, `cv_analysis` (adapter from Plan 1), `rag` (Task 5), `market` (adapter), `coaching` (built via `build_coaching_graph`), `critic`, `application_send`, `aggregate`. Edges: `START→router`; `router` conditionally fans to the planned agents; planned agents → `critic`; `critic_route` → (`regenerate`→back to router/first agent | `escalate`→`application_send` as HITL escalation | `accept`→`aggregate`); `aggregate→END`. Compile with the passed checkpointer.

- [ ] **Step 1:** Implement the builder. Map each agent name to its node callable; use `add_conditional_edges(START_or_router, fanout_or_route, [...])`. The aggregate node composes `final_answer` from namespaced outputs.
- [ ] **Step 2 (unit):** `test_supervisor_e2e.py::test_builds` (no DB) — `build_supervisor(None).get_graph().nodes` contains all expected node names. → PASS.
- [ ] **Step 3 (live, INFRA_UP=1):** with `checkpointer_cm()` and a stubbed/fast model, invoke a thread that routes to `market` only; assert a checkpoint is written and `final_answer` is set. → PASS.
- [ ] **Step 4:** ruff; commit `feat: supervisor graph wiring router/agents/critic/HITL/aggregate`.

---

### Task 10: End-to-end HITL pause/resume across a restart (integration)

**Files:** Extend `tests/integration/test_supervisor_e2e.py`.

- [ ] **Step 1 (live, INFRA_UP=1):** Build supervisor A with `checkpointer_cm()`, invoke a thread whose plan ends in `application_send`; assert the invoke returns an `__interrupt__` (paused) and the pending `hitl_request.kind == "application_send"`.
- [ ] **Step 2:** Build a FRESH supervisor B with a NEW checkpointer context (simulating a restart), resume the SAME `thread_id` with `Command(resume={"approved": True})`; assert it completes and `application.status == "APPROVED"`. This proves durability (§19 success criterion).
- [ ] **Step 3:** ruff; commit `test: e2e HITL pause survives restart and resumes`.

---

## Plan 2 self-review

- **Spec coverage:** RAG over uploaded docs (§7) ✓ Tasks 2–5; web-search agent already exists from Plan 1; Supervisor + routing (§5,§6.0) ✓ Tasks 6,9; Critic loop (§6.7) ✓ Task 7; HITL interrupt + durable resume (§9,§19) ✓ Tasks 8,10; Postgres checkpointer wired (§11) ✓ Task 9. Per-user RAG isolation (§7) ✓ Task 3.
- **Placeholders:** none — interfaces and key logic specified; routine bodies are TDD-driven.
- **Type consistency:** `CopilotState`, `RoutingDecision`, `CriticVerdict`, `HitlRequest`, `build_supervisor(checkpointer)`, `rag_node`/`critic_node`/`application_send_node` signatures are consistent across tasks.
- **Risk:** Critic + regenerate fan-out multiplies LLM calls — `MAX_CRITIC_RETRIES=2` caps it; routing uses the `fast` model. Live tests gated by `INFRA_UP=1`.
