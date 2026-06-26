"""Infrastructure-gated integration tests.

These tests require live Postgres / Qdrant and are skipped unless
INFRA_UP=1 is set in the environment.

To run manually (after `podman compose up -d`):
    INFRA_UP=1 uv run pytest tests/integration -v
"""

from __future__ import annotations

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


def test_alembic_upgrade_head_creates_tables() -> None:
    """Run alembic upgrade head and verify all six tables exist in the DB."""
    import subprocess

    from sqlalchemy import create_engine, inspect, text

    from app.core.config import get_settings
    from app.services.session import sqlalchemy_url  # noqa: PLC0415

    # Reset schema first so prior tests (e.g. coaching ensure_schema) don't leave
    # conflicting tables that block the migration.
    _settings = get_settings()
    _engine_pre = create_engine(sqlalchemy_url(_settings.database_url))
    with _engine_pre.begin() as _conn:
        _conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    _engine_pre.dispose()

    # Run the migration
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
    )

    # Verify tables exist
    engine = create_engine(sqlalchemy_url(_settings.database_url))
    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())

    expected = {"users", "documents", "jobs", "matches", "applications", "runs"}
    missing = expected - existing_tables
    assert not missing, f"Missing tables after migration: {missing}"

    # Cleanup: drop and recreate schema for test isolation
    engine = create_engine(sqlalchemy_url(_settings.database_url))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))


def test_longterm_remember_recall_persistence():
    """remember + recall round-trips via PostgresStore across two separate store_cm opens.

    This proves that facts are truly persisted (not just in-memory) because we
    write in one context-manager session and read in a second, independent one.
    """
    import uuid

    from app.memory.longterm import recall, remember

    user_id = f"test_lt_{uuid.uuid4().hex[:8]}"

    # --- Write in one context-manager session ---
    remember(user_id, "career_goal", "Staff Engineer at a fintech")
    remember(user_id, "preferred_country", "UAE")
    remember(user_id, "salary_expectation", 300_000)

    # --- Read in a completely separate context-manager session ---
    facts = recall(user_id)

    assert facts.get("career_goal") == "Staff Engineer at a fintech", (
        f"Expected career_goal to be persisted, got: {facts}"
    )
    assert facts.get("preferred_country") == "UAE", (
        f"Expected preferred_country to be persisted, got: {facts}"
    )
    assert facts.get("salary_expectation") == 300_000, (
        f"Expected salary_expectation to be persisted, got: {facts}"
    )


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
