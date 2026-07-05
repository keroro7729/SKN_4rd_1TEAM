"""Read-only storage diagnostics helpers for management commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.db import connection


CORE_MODEL_LABELS = (
    "accounts.CustomUser",
    "problems.ProblemCategory",
    "problems.ProblemTag",
    "problems.Problem",
    "problems.TestCase",
    "submissions.Submission",
    "submissions.ExecutionJob",
    "wrongnotes.WrongNote",
    "wrongnotes.WrongNoteVector",
    "logs.LLMRequestLog",
    "logs.ErrorLog",
    "gamification.PointLog",
    "gamification.Mission",
    "gamification.UserMission",
    "notices.Notice",
)


@dataclass(frozen=True)
class CoreTable:
    label: str
    table_name: str


def get_core_tables() -> list[CoreTable]:
    tables = []
    for label in CORE_MODEL_LABELS:
        model = apps.get_model(label)
        tables.append(CoreTable(label=label, table_name=model._meta.db_table))
    return tables


def get_database_info() -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("select current_database(), current_user, version()")
        database, user, version = cursor.fetchone()
    return {
        "current_database": database,
        "current_user": user,
        "postgresql_version": version,
    }


def list_public_tables() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
              and table_type = 'BASE TABLE'
            order by table_name
            """
        )
        return [row[0] for row in cursor.fetchall()]


def get_columns(table_name: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select column_name, data_type, is_nullable, column_default
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
            order by ordinal_position
            """,
            [table_name],
        )
        return [
            {
                "column_name": row[0],
                "data_type": row[1],
                "is_nullable": row[2],
                "column_default": row[3],
            }
            for row in cursor.fetchall()
        ]


def get_row_count(table_name: str) -> int:
    quoted_table = connection.ops.quote_name(table_name)
    with connection.cursor() as cursor:
        cursor.execute(f"select count(*) from {quoted_table}")
        return int(cursor.fetchone()[0])
