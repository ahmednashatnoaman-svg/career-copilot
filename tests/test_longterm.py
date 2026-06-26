"""Unit tests for app.memory.longterm — remember / recall round-trip.

Uses a deterministic in-memory fake store so no live Postgres is needed.
The fake is injected by monkeypatching ``app.memory.longterm.store_cm``.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

# ---------------------------------------------------------------------------
# Fake store (in-memory)
# ---------------------------------------------------------------------------

class _FakeStore:
    """Minimal in-memory stand-in for PostgresStore."""

    def __init__(self) -> None:
        # { (namespace, key): value_dict }
        self._data: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}

    def put(self, namespace: tuple[str, ...], key: str, value: dict[str, Any]) -> None:
        self._data[(namespace, key)] = value

    def search(self, namespace_prefix: tuple[str, ...]) -> list[_FakeItem]:
        results = []
        for (ns, key), value in self._data.items():
            if ns == namespace_prefix:
                results.append(_FakeItem(key=key, value=value))
        return results


class _FakeItem:
    def __init__(self, *, key: str, value: dict[str, Any]) -> None:
        self.key = key
        self.value = value


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------

def _make_fake_store_cm(fake: _FakeStore):
    """Return a context-manager factory that yields *fake*."""

    @contextmanager
    def _cm():
        yield fake

    return _cm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_remember_then_recall_round_trips_single_value(monkeypatch):
    """remember then recall must return the same value for the same key."""
    import app.memory.longterm as lt

    fake = _FakeStore()
    monkeypatch.setattr(lt, "store_cm", _make_fake_store_cm(fake))

    lt.remember("u1", "career_goal", "senior ML engineer")

    facts = lt.recall("u1")
    assert facts == {"career_goal": "senior ML engineer"}


def test_remember_multiple_keys(monkeypatch):
    """All stored keys must appear in the recalled dict."""
    import app.memory.longterm as lt

    fake = _FakeStore()
    monkeypatch.setattr(lt, "store_cm", _make_fake_store_cm(fake))

    lt.remember("u2", "career_goal", "VP of Engineering")
    lt.remember("u2", "preferred_country", "UAE")
    lt.remember("u2", "salary_expectation", 250_000)

    facts = lt.recall("u2")
    assert facts["career_goal"] == "VP of Engineering"
    assert facts["preferred_country"] == "UAE"
    assert facts["salary_expectation"] == 250_000


def test_user_isolation(monkeypatch):
    """recall(user_a) must not return user_b's facts."""
    import app.memory.longterm as lt

    fake = _FakeStore()
    monkeypatch.setattr(lt, "store_cm", _make_fake_store_cm(fake))

    lt.remember("alice", "career_goal", "data scientist")
    lt.remember("bob", "career_goal", "product manager")

    alice_facts = lt.recall("alice")
    bob_facts = lt.recall("bob")

    assert alice_facts == {"career_goal": "data scientist"}
    assert bob_facts == {"career_goal": "product manager"}


def test_recall_empty_store(monkeypatch):
    """recall on an empty store must return an empty dict (no error)."""
    import app.memory.longterm as lt

    fake = _FakeStore()
    monkeypatch.setattr(lt, "store_cm", _make_fake_store_cm(fake))

    facts = lt.recall("nobody")
    assert facts == {}


def test_recall_graceful_on_store_error(monkeypatch):
    """recall must return {} when the store raises (graceful degradation)."""
    import app.memory.longterm as lt

    @contextmanager
    def _failing_cm():
        raise RuntimeError("DB is down")
        yield

    monkeypatch.setattr(lt, "store_cm", _failing_cm)

    facts = lt.recall("u_error")
    assert facts == {}


def test_remember_survives_store_error(monkeypatch):
    """remember must not raise when the store is unavailable."""
    import app.memory.longterm as lt

    @contextmanager
    def _failing_cm():
        raise RuntimeError("DB is down")
        yield

    monkeypatch.setattr(lt, "store_cm", _failing_cm)

    # Must not raise
    lt.remember("u_error", "key", "value")
