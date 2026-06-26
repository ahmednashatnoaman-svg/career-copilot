from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from app.core.config import get_settings


@contextmanager
def checkpointer_cm():
    with PostgresSaver.from_conn_string(get_settings().database_url) as cp:
        cp.setup()
        yield cp


@contextmanager
def store_cm():
    with PostgresStore.from_conn_string(get_settings().database_url) as store:
        store.setup()
        yield store
