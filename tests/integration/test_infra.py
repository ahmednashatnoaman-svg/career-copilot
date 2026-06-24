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
