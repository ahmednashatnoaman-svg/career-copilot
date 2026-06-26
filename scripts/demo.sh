#!/usr/bin/env bash
# scripts/demo.sh — end-to-end Career Copilot demo
#
# Prerequisites:
#   1. Stack is running:  podman-compose -f infra/compose.yaml up -d
#   2. .env contains real API keys (GROQ_API_KEY, GOOGLE_API_KEY, TAVILY_API_KEY,
#      LANGCHAIN_API_KEY).  Without real keys the LLM calls will fail.
#
# What it does:
#   Step 1 — health-check the backend
#   Step 2 — upload a sample resume PDF
#   Step 3 — start a Supervisor run with a real job-search headline
#   Step 4 — poll until the run pauses at the HITL approval gate (or completes)
#
# Usage:
#   bash scripts/demo.sh [API_BASE]
#   Default API_BASE = http://localhost:8000

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
SAMPLE_RESUME="${BASH_SOURCE%/*}/../tests/fixtures/sample_resume.pdf"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
info()  { printf '\n\033[1;34m[demo]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m  ✓\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m  !\033[0m  %s\n' "$*"; }
die()   { printf '\033[1;31m[demo] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }
require_cmd curl
require_cmd jq

# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Health check
# ──────────────────────────────────────────────────────────────────────────────
info "Step 1 — checking backend health at ${API_BASE}/health"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/health")
if [ "${HTTP_STATUS}" != "200" ]; then
  die "Backend not healthy (HTTP ${HTTP_STATUS}).  Is the stack running?
  Run:  podman-compose -f infra/compose.yaml up -d"
fi
ok "Backend healthy (HTTP 200)"

# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Upload a sample resume
# ──────────────────────────────────────────────────────────────────────────────
info "Step 2 — uploading sample resume"

if [ ! -f "${SAMPLE_RESUME}" ]; then
  warn "Sample resume not found at ${SAMPLE_RESUME}; creating a placeholder text file."
  SAMPLE_RESUME="/tmp/demo_resume_$(date +%s).txt"
  cat > "${SAMPLE_RESUME}" <<'EOF'
John Doe | john.doe@example.com | github.com/johndoe
Senior Software Engineer — 5 years Python, FastAPI, LangChain, ML pipelines.
Experience: TechCorp (2021–present), StartupXYZ (2019–2021).
Education: BSc Computer Science.
Skills: Python, FastAPI, LangChain, LangGraph, Postgres, Docker, AWS.
EOF
fi

UPLOAD_RESPONSE=$(curl -s -X POST "${API_BASE}/documents" \
  -H "Accept: application/json" \
  -F "file=@${SAMPLE_RESUME}" || true)

echo "Upload response: ${UPLOAD_RESPONSE}" | head -5
DOC_ID=$(echo "${UPLOAD_RESPONSE}" | jq -r '.id // .document_id // "unknown"' 2>/dev/null || echo "unknown")
ok "Resume uploaded (doc_id=${DOC_ID})"

# ──────────────────────────────────────────────────────────────────────────────
# Step 3: Start a Supervisor run
# ──────────────────────────────────────────────────────────────────────────────
info "Step 3 — starting a Supervisor run"

HEADLINE="Find remote AI engineer jobs in Europe and tailor an application"

RUN_PAYLOAD=$(jq -n \
  --arg msg "${HEADLINE}" \
  --arg doc "${DOC_ID}" \
  '{user_message: $msg, document_ids: [$doc]}')

RUN_RESPONSE=$(curl -s -X POST "${API_BASE}/runs" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "${RUN_PAYLOAD}" || true)

echo "Run response: ${RUN_RESPONSE}" | head -5
RUN_ID=$(echo "${RUN_RESPONSE}" | jq -r '.run_id // .id // "unknown"' 2>/dev/null || echo "unknown")
ok "Run started (run_id=${RUN_ID})"

# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Poll for HITL pause or completion
# ──────────────────────────────────────────────────────────────────────────────
info "Step 4 — polling run status (max 30 × 5s)"

MAX_POLLS=30
POLL_INTERVAL=5

for i in $(seq 1 "${MAX_POLLS}"); do
  STATUS_RESPONSE=$(curl -s "${API_BASE}/runs/${RUN_ID}" \
    -H "Accept: application/json" || true)
  STATUS=$(echo "${STATUS_RESPONSE}" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")

  printf '  poll %2d/%d  status=%s\n' "${i}" "${MAX_POLLS}" "${STATUS}"

  case "${STATUS}" in
    "awaiting_approval"|"hitl_paused"|"interrupted")
      ok "Run paused at HITL approval gate (status=${STATUS})"
      warn "To approve the draft application, call:"
      warn "  POST ${API_BASE}/runs/${RUN_ID}/resume"
      warn '  body: {"approved": true}'
      break
      ;;
    "completed"|"success"|"done")
      ok "Run completed successfully (status=${STATUS})"
      RESULT=$(echo "${STATUS_RESPONSE}" | jq -r '.result // .output // "(see response body)"' 2>/dev/null | head -5)
      info "Result preview: ${RESULT}"
      break
      ;;
    "failed"|"error")
      warn "Run failed (status=${STATUS}).  Check API logs."
      warn "Hint: ensure GROQ_API_KEY / GOOGLE_API_KEY are set in .env"
      break
      ;;
    *)
      # still running — wait and retry
      sleep "${POLL_INTERVAL}"
      ;;
  esac
done

# ──────────────────────────────────────────────────────────────────────────────
info "Demo complete.  Dashboard: http://localhost:3000"
