"""Shared pytest fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _disable_supabase_auth(monkeypatch):
    """Null out the Supabase client so the JWT middleware skips auth in tests.

    The jwt_auth_middleware in app/main.py calls get_client() and only
    enforces auth when it returns a non-None client.  Tests don't carry
    real JWTs, so we patch get_client to return None for the entire test run.
    """
    import app.services.supabase_db as db_mod

    monkeypatch.setattr(db_mod, "_client", None)
    monkeypatch.setattr(db_mod, "get_client", lambda: None)


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch, request):
    """Mock FastEmbed for fast tests, skip if marked @pytest.mark.slow."""
    if "slow" in request.node.keywords:
        return
    import app.rag.embeddings as embeddings_mod
    monkeypatch.setattr(
        embeddings_mod,
        "embed_texts",
        lambda texts: [[0.1] * embeddings_mod.EMBED_DIM for _ in texts]
    )
