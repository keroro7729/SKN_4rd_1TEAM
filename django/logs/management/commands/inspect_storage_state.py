"""Summarize PostgreSQL and VectorDB storage state."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

from ._storage_helpers import get_core_tables, get_row_count, list_public_tables
from ._vector_helpers import call_vector_diagnostics


class Command(BaseCommand):
    help = "Print PASS/WARN/FAIL storage diagnostics for PostgreSQL and ChromaDB."

    def _line(self, level: str, message: str):
        self.stdout.write(f"{level}: {message}")

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                cursor.fetchone()
            self._line("PASS", "PostgreSQL connection ok")
        except Exception as exc:
            self._line("FAIL", f"PostgreSQL connection failed: {exc.__class__.__name__}")
            return

        public_tables = set(list_public_tables())
        core_tables = get_core_tables()
        for table in core_tables:
            if table.table_name in public_tables:
                self._line("PASS", f"{table.table_name} exists")
            else:
                self._line("FAIL", f"{table.table_name} missing")

        for table_name in (
            "problems_problem",
            "problems_testcase",
            "submissions_executionjob",
        ):
            if table_name not in public_tables:
                self._line("FAIL", f"{table_name} missing")
                continue
            count = get_row_count(table_name)
            level = (
                "PASS"
                if count > 0 or table_name == "submissions_executionjob"
                else "WARN"
            )
            self._line(level, f"{table_name} rows={count}")

        vector = call_vector_diagnostics()
        if not vector.ok:
            self._line("WARN", f"VectorDB diagnostics unavailable: {vector.message}")
            return

        required = (vector.data or {}).get("required") or {}
        if required.get("exists"):
            self._line("PASS", "wrong_note_embeddings collection exists")
        else:
            self._line("WARN", "wrong_note_embeddings collection not found")

        forbidden = (vector.data or {}).get("forbidden") or {}
        for name, state in forbidden.items():
            if state.get("exists"):
                self._line("FAIL", f"forbidden collection exists: {name}")
            else:
                self._line("PASS", f"forbidden collection absent: {name}")
