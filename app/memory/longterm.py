"""Long-term user memory via LangGraph PostgresStore.

Public interface
----------------
    remember(user_id, key, value) -> None
        Persist an arbitrary fact under namespace ("user", user_id) / key.

    recall(user_id) -> dict
        Return all stored facts for the user as {key: value, ...}.
        Returns an empty dict when no facts exist or when the store is
        unavailable (graceful degradation).

Both functions use ``store_cm()`` from ``app.memory.checkpointer`` — they
never open ad-hoc database connections.
"""

from __future__ import annotations

import logging
from typing import Any

from app.memory.checkpointer import store_cm

logger = logging.getLogger(__name__)


def remember(user_id: str, key: str, value: Any) -> None:
    """Persist *value* under namespace ``("user", user_id)`` with *key*.

    Args:
        user_id: Identifies the user (namespace discriminator).
        key: Fact name, e.g. "career_goal", "preferred_country".
        value: Any JSON-serialisable value.  Stored as ``{"v": value}``
               to satisfy the store's ``dict`` requirement.
    """
    try:
        with store_cm() as store:
            store.put(("user", user_id), key, {"v": value})
    except Exception:
        logger.exception("longterm.remember failed for user=%s key=%s", user_id, key)


def recall(user_id: str) -> dict:
    """Return all stored facts for *user_id* as ``{key: value, ...}``.

    Uses ``store.search(("user", user_id))`` which returns every item in the
    namespace.  The inner ``{"v": ...}`` wrapper is unwrapped transparently.

    Returns an empty dict on any error so callers can degrade gracefully.
    """
    try:
        with store_cm() as store:
            items = store.search(("user", user_id))
            return {item.key: item.value.get("v", item.value) for item in items}
    except Exception:
        logger.exception("longterm.recall failed for user=%s", user_id)
        return {}
