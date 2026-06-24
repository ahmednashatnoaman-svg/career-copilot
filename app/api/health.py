from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}
