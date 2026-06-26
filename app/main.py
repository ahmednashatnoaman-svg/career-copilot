from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.applications import router as applications_router
from app.api.coaching import router as coaching_router
from app.api.cv import router as cv_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.interviews import router as interviews_router
from app.api.matches import router as matches_router
from app.api.runs import router as runs_router
from app.core.tracing import configure_tracing


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    configure_tracing()
    _try_init_supervisor()
    yield


app = FastAPI(title="AI Career Copilot", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# JWT Auth middleware — only active when Supabase is configured
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next):
    """Verify Supabase JWT on all non-public routes.

    Skipped entirely when SUPABASE_URL is not set (local dev / CI without keys).
    """
    from app.services.supabase_db import get_client  # noqa: PLC0415

    db = get_client()
    if db is None:
        return await call_next(request)

    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/docs"):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing auth token"})

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        user_resp = db.auth.get_user(token)
        if not user_resp or not user_resp.user:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        request.state.user_id = user_resp.user.id
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=401, content={"detail": "Token verification failed"})

    return await call_next(request)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"status": "ok", "service": "AI Career Copilot API", "docs": "/docs"}


app.include_router(health_router)
app.include_router(documents_router)
app.include_router(runs_router)
app.include_router(applications_router)
app.include_router(coaching_router)
app.include_router(interviews_router)
app.include_router(cv_router)
app.include_router(matches_router)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Supervisor init helper
# ---------------------------------------------------------------------------


def _try_init_supervisor() -> None:
    """Initialise the supervisor graph with Postgres checkpointer if DB is reachable.

    Silently skips if the DB is unavailable (e.g. in unit-test environments
    where INFRA_UP is not set). Tests inject a stub via
    ``app.api.runs.set_supervisor()``.
    """
    if os.getenv("INFRA_UP") != "1":
        return

    try:
        from app.api.runs import set_supervisor  # noqa: PLC0415
        from app.memory.checkpointer import checkpointer_cm  # noqa: PLC0415
        from app.orchestrator.supervisor import build_supervisor  # noqa: PLC0415

        # NOTE: checkpointer_cm is a context manager; we enter it here and
        # intentionally keep it open for the lifetime of the process.
        # This is acceptable for a long-running server.
        _cm = checkpointer_cm()
        checkpointer = _cm.__enter__()
        graph = build_supervisor(checkpointer=checkpointer)
        set_supervisor(graph)
    except Exception:  # noqa: BLE001
        # DB unavailable — supervisor remains None; unit tests are unaffected.
        pass
