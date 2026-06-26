"""Unit tests for SQLAlchemy models — no live DB required."""

from __future__ import annotations

from app.models.db import ApplicationStatus, Base

EXPECTED_TABLES = {"users", "documents", "jobs", "matches", "applications", "runs"}
EXPECTED_STATUS_VALUES = {"DRAFT", "APPROVED", "SENT", "REJECTED", "HUMAN_REQUIRED"}


def test_all_six_tables_registered() -> None:
    """Base.metadata must expose all six domain tables."""
    registered = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES.issubset(registered), (
        f"Missing tables: {EXPECTED_TABLES - registered}"
    )


def test_applications_status_column_is_enum() -> None:
    """The applications.status column must use the ApplicationStatus enum."""
    table = Base.metadata.tables["applications"]
    status_col = table.c["status"]
    col_type = status_col.type
    # SQLAlchemy wraps Python enums in its own Enum type
    assert hasattr(col_type, "enum_class"), (
        "applications.status column type must be an Enum with enum_class"
    )
    assert col_type.enum_class is ApplicationStatus


def test_application_status_enum_values() -> None:
    """ApplicationStatus must expose exactly the five canonical values."""
    actual = {member.value for member in ApplicationStatus}
    assert actual == EXPECTED_STATUS_VALUES, (
        f"Status mismatch — got {actual}, expected {EXPECTED_STATUS_VALUES}"
    )


def test_all_models_have_created_at() -> None:
    """Every table must have a created_at column."""
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        col_names = {c.name for c in table.c}
        assert "created_at" in col_names, (
            f"Table '{table_name}' is missing 'created_at' column"
        )


def test_all_models_have_id_pk() -> None:
    """Every table must have an 'id' primary-key column."""
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        pk_names = {c.name for c in table.primary_key.columns}
        assert "id" in pk_names, (
            f"Table '{table_name}' is missing 'id' primary key"
        )
