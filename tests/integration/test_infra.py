import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("INFRA_UP") != "1", reason="infra not running")


def test_qdrant_reachable():
    from app.core.clients import get_qdrant

    assert get_qdrant().get_collections() is not None


def test_postgres_reachable():
    import psycopg

    from app.core.config import get_settings

    with psycopg.connect(get_settings().database_url, connect_timeout=3) as conn:
        assert conn.execute("select 1").fetchone()[0] == 1


def test_checkpointer_setup():
    from app.memory.checkpointer import checkpointer_cm

    with checkpointer_cm() as cp:
        assert cp is not None


def test_rag_store_per_user_isolation():
    """Upsert docs for two users; each user's query must not return the other's payloads."""
    from app.rag.store import ensure_collection, query, upsert_chunks

    ensure_collection()

    user_a_chunks = ["alpha chunk one", "alpha chunk two", "alpha chunk three"]
    user_b_chunks = ["beta chunk one", "beta chunk two", "beta chunk three"]

    upsert_chunks("user_a", "doc_a", user_a_chunks)
    upsert_chunks("user_b", "doc_b", user_b_chunks)

    results_a = query("user_a", "alpha chunk", top_k=10)
    results_b = query("user_b", "beta chunk", top_k=10)

    # user_a results must never contain user_b payloads
    for hit in results_a:
        assert hit["doc_id"] != "doc_b", (
            f"user_a query returned user_b payload: {hit}"
        )

    # user_b results must never contain user_a payloads
    for hit in results_b:
        assert hit["doc_id"] != "doc_a", (
            f"user_b query returned user_a payload: {hit}"
        )
