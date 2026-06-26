from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.coaching.embeddings import build_embedding_service
from app.agents.coaching.graph import CareerCoachingAgent
from app.agents.coaching.memory import PostgresMemory
from app.agents.coaching.observability import (
    configure_logging,
    log_event,
    new_request_id,
    now_ms,
    set_request_id,
)
from app.agents.coaching.rate_limit import InMemoryRateLimiter
from app.agents.coaching.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    SessionResetRequest,
    SessionResetResponse,
)
from app.agents.coaching.settings import get_settings

configure_logging()
logger = logging.getLogger("career_coaching_agent.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    embeddings = build_embedding_service(settings)
    memory = PostgresMemory(settings, embeddings)
    app.state.settings = settings
    app.state.memory = memory
    app.state.agent = None
    app.state.startup_error = None
    app.state.rate_limiter = InMemoryRateLimiter(settings.rate_limit_requests_per_minute)

    try:
        memory.ensure_schema()
        app.state.agent = CareerCoachingAgent(settings, memory)
    except Exception as exc:
        app.state.startup_error = str(exc)

    yield

    agent = getattr(app.state, "agent", None)
    if agent is not None:
        agent.close()


app = FastAPI(title="Career Coaching Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    set_request_id(request_id)
    request.state.request_id = request_id
    start = now_ms()
    log_event(
        logger,
        "request_started",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round(now_ms() - start, 2)
        log_event(
            logger,
            "request_failed",
            level=logging.ERROR,
            path=request.url.path,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise
    duration_ms = round(now_ms() - start, 2)
    response.headers["X-Request-ID"] = request_id
    log_event(
        logger,
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "request_id": request_id,
                "code": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
            }
        },
        headers={"X-Request-ID": request_id or ""},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    log_event(
        logger,
        "unhandled_exception",
        level=logging.ERROR,
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "request_id": request_id,
                "code": "internal_server_error",
                "message": "Unexpected server error.",
                "status_code": 500,
            }
        },
        headers={"X-Request-ID": request_id or ""},
    )


@app.get("/")
def root():
    return {
        "service": "career_coaching_agent",
        "status_endpoint": "/health",
        "chat_endpoint": "/api/chat",
        "session_reset_endpoint": "/api/session/reset",
    }


@app.get("/health", response_model=HealthResponse)
def health():
    memory: PostgresMemory | None = getattr(app.state, "memory", None)
    if memory is None:
        return HealthResponse(
            status="degraded",
            database=False,
            agent_ready=False,
            llm_configured=False,
            detail="Application startup has not completed.",
        )

    agent: CareerCoachingAgent | None = getattr(app.state, "agent", None)
    agent_ready = agent is not None
    settings = app.state.settings
    detail = getattr(app.state, "startup_error", None)
    database_ok = False if detail and not agent_ready else memory.ping()
    return HealthResponse(
        status="ok" if database_ok and agent_ready else "degraded",
        database=database_ok,
        agent_ready=agent_ready,
        llm_configured=bool(settings.groq_api_key),
        langsmith_tracing=settings.langsmith_tracing,
        detail=detail,
    )


@app.post("/api/chat", response_model=ChatResponse, responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def chat(request: ChatRequest, http_request: Request):
    _enforce_rate_limit(http_request, request.user_id)
    agent: CareerCoachingAgent | None = getattr(app.state, "agent", None)
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail=f"Agent is not ready. {getattr(app.state, 'startup_error', None) or 'Check Postgres and configuration.'}",
        )
    log_event(logger, "chat_started", user_id=request.user_id, thread_id=request.thread_id, mode=request.mode)
    response = agent.invoke(request)
    response.request_id = getattr(http_request.state, "request_id", None)
    log_event(
        logger,
        "chat_completed",
        user_id=request.user_id,
        thread_id=request.thread_id,
        sub_intent=response.sub_intent,
        next_action=response.next_action,
    )
    return response


@app.post("/api/session/reset", response_model=SessionResetResponse, responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def reset_session(request: SessionResetRequest, http_request: Request):
    _enforce_rate_limit(http_request, request.user_id)
    memory: PostgresMemory | None = getattr(app.state, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="Memory store is not ready.")
    graph_thread_id = f"{request.user_id}:{request.thread_id}"
    deleted = memory.clear_session(request.user_id, request.thread_id, graph_thread_id)
    return SessionResetResponse(
        status="ok",
        request_id=getattr(http_request.state, "request_id", None),
        user_id=request.user_id,
        thread_id=request.thread_id,
        deleted=deleted,
    )


def _enforce_rate_limit(request: Request, user_id: str) -> None:
    limiter: InMemoryRateLimiter | None = getattr(app.state, "rate_limiter", None)
    if limiter is None:
        return
    client_host = request.client.host if request.client else "unknown"
    key = f"{user_id}:{client_host}"
    allowed, retry_after = limiter.allow(key)
    if not allowed:
        log_event(logger, "rate_limit_exceeded", user_id=user_id, client=client_host, retry_after=retry_after)
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limit_exceeded",
                "message": "Too many requests. Try again later.",
                "retry_after_seconds": retry_after,
            },
        )
