from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.agents.coaching.embeddings import EmbeddingService, vector_literal
from app.agents.coaching.settings import Settings


class PostgresMemory:
    def __init__(self, settings: Settings, embeddings: EmbeddingService) -> None:
        self.settings = settings
        self.embeddings = embeddings

    def connect(self):
        return psycopg.connect(
            self.settings.database_url,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=self.settings.database_connect_timeout_seconds,
        )

    def ping(self) -> bool:
        try:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS ok")
                    return cur.fetchone()["ok"] == 1
        except Exception:
            return False

    def ensure_schema(self) -> None:
        dimension = int(self.embeddings.dimension)
        statements = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT,
                profile JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS conversations_user_thread_idx
            ON conversations (user_id, thread_id, created_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                thread_id TEXT NOT NULL,
                target_role TEXT,
                interview_type TEXT,
                level TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                current_question TEXT,
                question_number INTEGER NOT NULL DEFAULT 0,
                max_questions INTEGER NOT NULL DEFAULT 5,
                summary JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS interview_sessions_active_idx
            ON interview_sessions (user_id, thread_id, status, updated_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS interview_turns (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                question_number INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                feedback JSONB NOT NULL DEFAULT '{}'::jsonb,
                score NUMERIC,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS career_plans (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                thread_id TEXT NOT NULL,
                plan_type TEXT NOT NULL,
                target_role TEXT,
                content JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS memory_items (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                thread_id TEXT,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding vector({dimension}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS memory_items_user_kind_idx
            ON memory_items (user_id, kind, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS memory_items_embedding_idx
            ON memory_items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            """,
        ]

        with self.connect() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)

    def upsert_user_profile(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        clean_profile = {key: value for key, value in profile.items() if value not in (None, "", [])}
        name = clean_profile.get("name")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, name, profile)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET
                        name = COALESCE(EXCLUDED.name, users.name),
                        profile = users.profile || EXCLUDED.profile,
                        updated_at = NOW()
                    RETURNING profile
                    """,
                    (user_id, name, Jsonb(clean_profile)),
                )
                row = cur.fetchone()
        return dict(row["profile"] or {})

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT profile FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
        return dict(row["profile"] or {}) if row else {}

    def add_message(
        self,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (user_id, thread_id, role, content, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, thread_id, role, content, Jsonb(metadata or {})),
                )

    def recent_messages(self, user_id: str, thread_id: str, limit: int = 12) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content, metadata, created_at
                    FROM conversations
                    WHERE user_id = %s AND thread_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, thread_id, limit),
                )
                rows = cur.fetchall()
        return list(reversed(rows))

    def close_active_interviews(self, user_id: str, thread_id: str, status: str = "replaced") -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE interview_sessions
                    SET status = %s, updated_at = NOW()
                    WHERE user_id = %s AND thread_id = %s AND status = 'active'
                    """,
                    (status, user_id, thread_id),
                )

    def create_interview_session(
        self,
        user_id: str,
        thread_id: str,
        target_role: str,
        interview_type: str,
        level: str,
        current_question: str,
        max_questions: int,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO interview_sessions (
                        user_id, thread_id, target_role, interview_type, level,
                        current_question, question_number, max_questions
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
                    RETURNING *
                    """,
                    (
                        user_id,
                        thread_id,
                        target_role,
                        interview_type,
                        level,
                        current_question,
                        max_questions,
                    ),
                )
                return dict(cur.fetchone())

    def active_interview(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM interview_sessions
                    WHERE user_id = %s AND thread_id = %s AND status = 'active'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (user_id, thread_id),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def update_interview_session(
        self,
        session_id: int,
        *,
        current_question: str | None = None,
        question_number: int | None = None,
        status: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> None:
        updates = []
        params: list[Any] = []
        if current_question is not None:
            updates.append("current_question = %s")
            params.append(current_question)
        if question_number is not None:
            updates.append("question_number = %s")
            params.append(question_number)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if summary is not None:
            updates.append("summary = %s")
            params.append(Jsonb(summary))
        if not updates:
            return

        updates.append("updated_at = NOW()")
        params.append(session_id)
        sql = f"UPDATE interview_sessions SET {', '.join(updates)} WHERE id = %s"
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def add_interview_turn(
        self,
        session_id: int,
        question_number: int,
        question: str,
        answer: str,
        feedback: dict[str, Any],
        score: int | float | None,
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO interview_turns (
                        session_id, question_number, question, answer, feedback, score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (session_id, question_number, question, answer, Jsonb(feedback), score),
                )

    def interview_turns(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT question_number, question, answer, feedback, score, created_at
                    FROM interview_turns
                    WHERE session_id = %s
                    ORDER BY question_number ASC, created_at ASC
                    """,
                    (session_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def store_career_plan(
        self,
        user_id: str,
        thread_id: str,
        plan_type: str,
        target_role: str | None,
        content: dict[str, Any],
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO career_plans (user_id, thread_id, plan_type, target_role, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, thread_id, plan_type, target_role, Jsonb(content)),
                )

    def add_memory_item(
        self,
        user_id: str,
        thread_id: str | None,
        kind: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        embedding = vector_literal(self.embeddings.embed(content))
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_items (user_id, thread_id, kind, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s::vector)
                    """,
                    (user_id, thread_id, kind, content, Jsonb(metadata or {}), embedding),
                )

    def search_memory(
        self,
        user_id: str,
        query: str,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        embedding = vector_literal(self.embeddings.embed(query))
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, thread_id, kind, content, metadata,
                           1 - (embedding <=> %s::vector) AS score,
                           created_at
                    FROM memory_items
                    WHERE user_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, user_id, embedding, limit),
                )
                return [dict(row) for row in cur.fetchall()]

    def clear_session(self, user_id: str, thread_id: str, graph_thread_id: str) -> dict[str, int]:
        deleted: dict[str, int] = {}
        statements = [
            (
                "checkpoint_writes",
                "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                (graph_thread_id,),
            ),
            (
                "checkpoint_blobs",
                "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                (graph_thread_id,),
            ),
            (
                "checkpoints",
                "DELETE FROM checkpoints WHERE thread_id = %s",
                (graph_thread_id,),
            ),
            (
                "career_plans",
                "DELETE FROM career_plans WHERE user_id = %s AND thread_id = %s",
                (user_id, thread_id),
            ),
            (
                "memory_items",
                "DELETE FROM memory_items WHERE user_id = %s AND thread_id = %s",
                (user_id, thread_id),
            ),
            (
                "interview_sessions",
                "DELETE FROM interview_sessions WHERE user_id = %s AND thread_id = %s",
                (user_id, thread_id),
            ),
            (
                "conversations",
                "DELETE FROM conversations WHERE user_id = %s AND thread_id = %s",
                (user_id, thread_id),
            ),
        ]
        with self.connect() as conn:
            with conn.cursor() as cur:
                for name, sql, params in statements:
                    cur.execute(sql, params)
                    deleted[name] = max(cur.rowcount or 0, 0)
        return deleted
