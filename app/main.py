from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

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

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    configure_tracing()
    # Supervisor graph is initialized lazily on first request to speed up cold start
    yield

app = FastAPI(title="AI Career Copilot", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Explicit origin allowlist — no regex, because allow_origin_regex + allow_credentials=True
# would let any Vercel app make credentialed requests to this backend (CSRF risk).
# Set FRONTEND_URL (production) and FRONTEND_URL_PREVIEW (PR preview) in the backend env.
_allowed_origins: list[str] = list(filter(None, [
    "http://localhost:3000",
    os.getenv("FRONTEND_URL", ""),
    os.getenv("FRONTEND_URL_PREVIEW", ""),
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# JWT Auth middleware — only active when Supabase is configured
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


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
        request.state.user_email = user_resp.user.email or ""
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


