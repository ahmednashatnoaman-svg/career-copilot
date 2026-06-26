from functools import lru_cache

from qdrant_client import QdrantClient

from app.core.config import get_settings


@lru_cache
def get_qdrant() -> QdrantClient:
    settings = get_settings()
    kwargs: dict = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return QdrantClient(**kwargs)
