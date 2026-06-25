# Frontend, Productionization & Release — Implementation Plan (Plan 4 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox steps; TDD where testable. Terminal step: superpowers:finishing-a-development-branch.

**Goal:** Ship the Next.js dashboard (upload, streaming copilot chat, matches, skill-gap, coaching, applications + HITL approval modals), long-term user memory, CI, free-tier hardening, docs, and a one-command Podman demo of the full stack.

**Architecture:** Next.js (App Router) + Tailwind + shadcn/ui talks to the FastAPI backend over REST + SSE. A typed API client and an `useSSE` hook stream graph events; interrupt events render approval modals that POST to `/runs/{id}/resume`. Long-term memory uses the LangGraph `PostgresStore` to persist user facts across threads. The whole system runs via one `podman-compose` file (backend, frontend, postgres, qdrant).

**Tech Stack:** Next.js 14+ (App Router, TS), Tailwind, shadcn/ui, EventSource/fetch-stream; backend `PostgresStore`; GitHub Actions; Podman.

**Depends on:** Plan 3 API (`/documents`, `/runs`, `/runs/{id}/stream`, `/runs/{id}/resume`, `/applications`).

**Parallelism:** Frontend pages (Tasks 3–6) are independent once the client+hook (Task 2) exist → parallelizable. Backend hardening (7,9) and CI/docs (8,10) run independent of the UI.

## Global Constraints

- All prior Global Constraints bind. Frontend lives in `frontend/`; one responsibility per component/file.
- The frontend NEVER calls LLM providers or job sites directly — only the FastAPI backend. Backend base URL via `NEXT_PUBLIC_API_BASE`.
- The SSE event contract from Plan 3 (`event: node|token|interrupt|done`) is the integration boundary; the `useSSE` hook is the only place that parses it.
- HITL: an `interrupt` event MUST render a blocking approval modal; nothing is "sent" without an explicit user click that POSTs to `/runs/{id}/resume`.
- Containers: Podman + `Containerfile`; the final `infra/compose.yaml` runs backend+frontend+postgres+qdrant with `podman-compose up`.
- CI must run ruff + pytest (unit/smoke; infra tests skipped) + `podman build` of both images on every push.
- Branch: `feat/frontend-release` off the Plan 3 branch; finish via finishing-a-development-branch.

---

## File structure

```
frontend/
  Containerfile  package.json  next.config.js  tailwind.config.ts  tsconfig.json
  app/{layout,page}.tsx
  app/onboarding/page.tsx  app/copilot/page.tsx  app/matches/page.tsx
  app/coaching/page.tsx  app/applications/page.tsx
  components/{ChatStream,ApprovalModal,MatchCard,SkillGapPanel,UploadDropzone,...}.tsx
  lib/api.ts          # typed API client
  lib/useSSE.ts       # SSE hook (the only SSE parser)
  lib/types.ts        # mirrors backend Pydantic contracts
app/memory/longterm.py # PostgresStore-backed user memory
.github/workflows/ci.yml
AGENTS.md  README.md  docs/architecture.md
```

---

### Task 1: Next.js scaffold + Containerfile + Tailwind + shadcn

**Files:** `frontend/*` base config, `frontend/app/{layout,page}.tsx`, `frontend/Containerfile`.

- [ ] **Step 1:** Scaffold `frontend/` (Next 14 App Router, TS, Tailwind); add shadcn/ui; a placeholder home page links to the five routes.
- [ ] **Step 2:** `frontend/Containerfile` (node:20-slim, `npm ci`, `npm run build`, `next start`); `.dockerignore` node_modules.
- [ ] **Step 3:** Verify `npm run build` succeeds; commit `feat: next.js dashboard scaffold + Containerfile`.

---

### Task 2: Typed API client + `useSSE` hook + types

**Files:** `frontend/lib/{api,useSSE,types}.ts`, `frontend/__tests__/useSSE.test.ts`.

**Interfaces — Produces:** `api.uploadDocument`, `api.startRun`, `api.resumeRun`, `api.listApplications`; `useSSE(threadId)` → `{events, status, interrupt}` parsing the `node|token|interrupt|done` stream; `types.ts` mirrors `RankedMatch/ApplicationPackage/HitlRequest/CareerPlan`.

- [ ] **Step 1 (RED):** Vitest test feeding a mock SSE stream of `node`→`interrupt`→ asserts `useSSE` exposes the `interrupt` payload and `status` transitions. → FAIL.
- [ ] **Step 2 (GREEN):** Implement client (fetch) + hook (ReadableStream reader parsing `event:`/`data:` frames). → PASS.
- [ ] **Step 3:** commit `feat: typed API client and SSE hook`.

---

### Task 3: Onboarding / upload page  *(parallel-safe)*

**Files:** `frontend/app/onboarding/page.tsx`, `components/UploadDropzone.tsx`.

- [ ] **Step 1:** Dropzone uploads resume/certs/portfolio via `api.uploadDocument`; shows ingested chunk counts; collects GitHub username + career goal (seed for long-term memory).
- [ ] **Step 2:** Manual check against running backend; commit `feat: onboarding + document upload page`.

---

### Task 4: Copilot chat (streaming + HITL)  *(parallel-safe)*

**Files:** `frontend/app/copilot/page.tsx`, `components/{ChatStream,ApprovalModal}.tsx`.

- [ ] **Step 1:** Chat input → `api.startRun` → `useSSE` renders streaming node/token updates; an `interrupt` event opens `ApprovalModal` showing the application package; Approve/Edit/Reject POSTs `api.resumeRun`.
- [ ] **Step 2:** Manual e2e against backend (start run → see stream → approve); commit `feat: streaming copilot chat with HITL approval modal`.

---

### Task 5: Matches + skill-gap + coaching pages  *(parallel-safe)*

**Files:** `frontend/app/matches/page.tsx`, `app/coaching/page.tsx`, `components/{MatchCard,SkillGapPanel}.tsx`.

- [ ] **Step 1:** Matches page renders `RankedMatch[]` (score + rationale + apply button → copilot); SkillGapPanel renders `market.skill_gaps`; Coaching page runs a mock-interview thread via the same SSE hook.
- [ ] **Step 2:** Manual check; commit `feat: matches, skill-gap, and coaching pages`.

---

### Task 6: Applications tracker  *(parallel-safe)*

**Files:** `frontend/app/applications/page.tsx`, `components/ApplicationRow.tsx`.

- [ ] **Step 1:** Table of `api.listApplications` with status badges (DRAFT/APPROVED/SENT/REJECTED/HUMAN_REQUIRED) + view cover letter/email.
- [ ] **Step 2:** Manual check; commit `feat: applications tracker page`.

---

### Task 7: Long-term memory via PostgresStore

**Files:** `app/memory/longterm.py`, wire into `app/orchestrator/supervisor.py`, `tests/test_longterm.py` + integration.

**Interfaces — Produces:** `remember(user_id, key, value)` / `recall(user_id) -> dict` over `store_cm()` namespace `("user", user_id)`; the router/aggregate read recalled facts (career goal, country, salary, skills, past applications) into prompts.

- [ ] **Step 1 (RED unit):** with a fake store, `remember`+`recall` round-trips a dict. → FAIL → implement → PASS.
- [ ] **Step 2 (live, INFRA_UP=1):** `store_cm()` round-trip across two contexts (persistence). → PASS.
- [ ] **Step 3:** commit `feat: long-term user memory via PostgresStore`.

---

### Task 8: GitHub Actions CI

**Files:** `.github/workflows/ci.yml`.

- [ ] **Step 1:** Workflow: on push/PR → setup uv → `uv sync` → `uv run ruff check` → `uv run pytest` (infra tests auto-skip) → `podman build` backend + `docker/podman build` frontend (use `redhat-actions/podman` or buildah action).
- [ ] **Step 2:** Validate YAML locally (`act` optional) ; commit `ci: ruff + pytest + container build workflow`.

---

### Task 9: Free-tier hardening (backoff + cache + fast-model routing)

**Files:** `app/llm/provider.py` (add retry/fallback), `app/llm/cache.py` (port `market_agent/tools/cache.py`), audit nodes for `fast` vs `reason`.

- [ ] **Step 1 (RED):** test that `get_llm` wraps calls with tenacity retry and that, on a primary-provider error, it falls back to the secondary provider (mock raising once). → FAIL.
- [ ] **Step 2 (GREEN):** Add `.with_retry(...)`/tenacity + provider fallback; add an LRU/disk response cache for deterministic (temperature=0) calls; switch routing/extraction/classification nodes to `get_llm("fast")`. → PASS.
- [ ] **Step 3:** commit `feat: llm backoff, provider fallback, response cache, fast-model routing`.

---

### Task 10: Docs + AGENTS.md + architecture diagram + demo script + final compose

**Files:** `AGENTS.md`, `README.md`, `docs/architecture.md`, `infra/compose.yaml` (add `frontend`), `scripts/demo.sh`.

- [ ] **Step 1:** `AGENTS.md` documents every subagent (role, inputs, outputs, tools) — the rubric's "Deep Agents behavior doc". `README.md`: full quickstart (`podman-compose up`, env, demo). `docs/architecture.md`: the §5 diagram + data flow. `scripts/demo.sh`: upload sample resume → run the headline query end-to-end.
- [ ] **Step 2:** Add the `frontend` service to `infra/compose.yaml` (depends_on backend); verify `podman-compose -f infra/compose.yaml up -d` brings up all four services and the UI reaches the API.
- [ ] **Step 3:** commit `docs: AGENTS.md, README, architecture, demo script + frontend compose service`.

---

### Task 11: Whole-branch review + finish

- [ ] **Step 1:** Run the final whole-branch code review (superpowers:requesting-code-review) over the merge-base..HEAD package; triage the accumulated Minor findings ledger.
- [ ] **Step 2:** Fix Critical/Important findings (one consolidated fix pass).
- [ ] **Step 3:** Verify success criteria (§19): `podman-compose up` full stack; upload→analyze→research→match→coach→application gated by HITL; interrupt survives restart; LangSmith traces; tests+CI green; all six rubric items demonstrable.
- [ ] **Step 4:** superpowers:finishing-a-development-branch (merge/PR).

---

## Plan 4 self-review

- **Spec coverage:** Next.js dashboard with all core pages (§12) ✓ T1,3–6; SSE + HITL modals (§9,§12) ✓ T2,4; long-term memory (§11) ✓ T7; Podman full-stack compose (§12) ✓ T1,10; CI (§15) ✓ T8; rate-limit hardening (§10,§18 #1) ✓ T9; AGENTS.md + docs (§2,§15) ✓ T10; success criteria + finish (§19) ✓ T11.
- **Placeholders:** none; UI tasks have concrete components + integration checks (UI is verified against the running backend rather than via unit asserts, which is appropriate).
- **Type consistency:** `frontend/lib/types.ts` mirrors `RankedMatch/ApplicationPackage/HitlRequest/CareerPlan`; `useSSE` is the single SSE contract consumer; `remember/recall` match the Store namespace.
- **Risk:** frontend scope in one phase is the tightest budget item — pages are deliberately thin and share one hook/client; defer polish to "future work" (§20).
