# AI Career Copilot

A supervisor multi-agent system that helps users navigate their career — analyzing CVs, researching job markets, matching opportunities, and generating tailored applications. Built with LangGraph, FastAPI, Groq (primary LLM), and Google Gemini (fallback).

## Quickstart

```bash
# 1. Install dependencies (creates .venv automatically)
uv sync

# 2. Copy env template and fill in your free API keys
cp .env.example .env

# 3. Start infrastructure (Postgres + Qdrant)
podman-compose -f infra/compose.yaml up -d

# 4. Run tests
uv run pytest

# 5. Start the API server
uv run uvicorn app.main:app --reload
```
