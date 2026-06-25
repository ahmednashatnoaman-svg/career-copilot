"""Supabase client for backend persistence.

Uses the service role key so all writes bypass RLS — the server is
responsible for verifying ownership before reading/writing.
"""
from __future__ import annotations

from supabase import Client, create_client

from app.core.config import get_settings

_client: Client | None = None


def get_client() -> Client | None:
    """Return a Supabase admin client, or None if Supabase is not configured."""
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def is_configured() -> bool:
    return get_client() is not None
