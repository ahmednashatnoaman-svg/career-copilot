from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.tracing import configure_tracing

app = FastAPI(title="AI Career Copilot")
app.include_router(health_router)


@app.on_event("startup")
def _startup() -> None:
    configure_tracing()
