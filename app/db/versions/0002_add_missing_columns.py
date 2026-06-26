"""Sync local schema with Supabase production schema.

Adds all columns that exist in the live Supabase tables but were absent
from the initial Alembic migration.  Running this migration against a
local PostgreSQL dev database makes it behave identically to Supabase
so that local tests hit the same schema the production API expects.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- documents: track how many chunks were indexed into Qdrant ---
    op.add_column("documents", sa.Column("chunks", sa.Integer(), nullable=True, server_default="0"))

    # --- jobs: record which data source the listing came from ---
    op.add_column("jobs", sa.Column("source", sa.String(255), nullable=True))

    # --- matches: store AI reasoning strings for each scored match ---
    op.add_column("matches", sa.Column("reasons", sa.ARRAY(sa.Text()), nullable=True))

    # --- runs: unique index on thread_id (used for SSE stream lookup) ---
    op.create_unique_constraint("uq_runs_thread_id", "runs", ["thread_id"])
    # Full run config — needed so any worker can hydrate the SSE stream
    op.add_column("runs", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("doc_ids", sa.ARRAY(sa.Text()), nullable=True))
    op.add_column("runs", sa.Column("resume_text", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("github_username", sa.String(255), nullable=True))
    op.add_column("runs", sa.Column("github_token", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("job_description", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    # --- applications: job_id is optional (applications may not link to a job record) ---
    op.alter_column("applications", "job_id", nullable=True)
    # Rename email → email_draft to match the Supabase column name and API usage
    op.alter_column("applications", "email", new_column_name="email_draft")
    op.add_column("applications", sa.Column("company", sa.String(512), nullable=True))
    op.add_column("applications", sa.Column("job_title", sa.String(512), nullable=True))
    op.add_column("applications", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "updated_at")
    op.drop_column("applications", "job_title")
    op.drop_column("applications", "company")
    op.alter_column("applications", "email_draft", new_column_name="email")
    op.alter_column("applications", "job_id", nullable=False)

    op.drop_column("runs", "completed_at")
    op.drop_column("runs", "job_description")
    op.drop_column("runs", "github_token")
    op.drop_column("runs", "github_username")
    op.drop_column("runs", "resume_text")
    op.drop_column("runs", "doc_ids")
    op.drop_column("runs", "message")
    op.drop_constraint("uq_runs_thread_id", "runs", type_="unique")

    op.drop_column("matches", "reasons")
    op.drop_column("jobs", "source")
    op.drop_column("documents", "chunks")
