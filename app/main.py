from fastapi import FastAPI

from app.api.applications import router as applications_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.core.tracing import configure_tracing

app = FastAPI(title="AI Career Copilot")
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(runs_router)
app.include_router(applications_router)


@app.on_event("startup")
def _startup() -> None:
    configure_tracing()
    _try_init_supervisor()


def _try_init_supervisor() -> None:
    """Initialise the supervisor graph with Postgres checkpointer if DB is reachable.

    Silently skips if the DB is unavailable (e.g. in unit-test environments
    where INFRA_UP is not set). Tests inject a stub via
    ``app.api.runs.set_supervisor()``.
    """
    import os  # noqa: PLC0415

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
