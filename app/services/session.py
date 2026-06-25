"""SQLAlchemy session factory and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def sqlalchemy_url(database_url: str) -> str:
    """Normalise a postgres URL to use the psycopg3 (psycopg) dialect.

    SQLAlchemy interprets a bare ``postgresql://`` scheme as psycopg2.
    This helper rewrites it to ``postgresql+psycopg://`` so that psycopg3
    is used instead.  An already-correct URL is returned unchanged.
    """
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        return database_url.replace("://", "+psycopg://", 1)
    return database_url


def _make_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    engine = create_engine(sqlalchemy_url(settings.database_url), pool_pre_ping=True)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


_SessionLocal: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal  # noqa: PLW0603
    if _SessionLocal is None:
        _SessionLocal = _make_session_factory()
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy Session per request."""
    factory = _get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
