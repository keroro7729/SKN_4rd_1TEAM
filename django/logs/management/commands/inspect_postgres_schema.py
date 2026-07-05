"""Inspect the active PostgreSQL schema without changing data."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from ._storage_helpers import (
    get_columns,
    get_core_tables,
    get_database_info,
    get_row_count,
    list_public_tables,
)


class Command(BaseCommand):
    help = "Inspect the current PostgreSQL schema and core table state."

    def add_arguments(self, parser):
        parser.add_argument("--core-only", action="store_true")
        parser.add_argument("--row-counts", action="store_true")
        parser.add_argument("--table")
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        public_tables = set(list_public_tables())
        core_tables = get_core_tables()
        core_table_names = {item.table_name for item in core_tables}

        if options["table"]:
            table_names = [options["table"]]
        elif options["core_only"]:
            table_names = [item.table_name for item in core_tables]
        else:
            table_names = sorted(public_tables)

        missing_requested_table = options["table"] and options["table"] not in public_tables
        if missing_requested_table and not options["as_json"]:
            self.stdout.write(f"[MISSING] {options['table']}")

        payload = {
            "database": get_database_info(),
            "core_tables": [
                {
                    "label": item.label,
                    "table_name": item.table_name,
                    "exists": item.table_name in public_tables,
                }
                for item in core_tables
            ],
            "tables": [],
        }

        for table_name in table_names:
            exists = table_name in public_tables
            table_payload = {
                "table_name": table_name,
                "is_core": table_name in core_table_names,
                "exists": exists,
                "row_count": None,
                "columns": [],
            }
            if exists:
                table_payload["columns"] = get_columns(table_name)
                if options["row_counts"]:
                    table_payload["row_count"] = get_row_count(table_name)
            payload["tables"].append(table_payload)

        if options["as_json"]:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        db = payload["database"]
        self.stdout.write("PostgreSQL")
        self.stdout.write(f"- database: {db['current_database']}")
        self.stdout.write(f"- user: {db['current_user']}")
        self.stdout.write(f"- version: {db['postgresql_version']}")
        self.stdout.write("")
        self.stdout.write("Core tables")
        for table in payload["core_tables"]:
            marker = "OK" if table["exists"] else "MISSING"
            self.stdout.write(f"- [{marker}] {table['table_name']} ({table['label']})")

        self.stdout.write("")
        self.stdout.write("Tables")
        for table in payload["tables"]:
            if not table["exists"]:
                self.stdout.write(f"\n[MISSING] {table['table_name']}")
                continue
            suffix = ""
            if table["row_count"] is not None:
                suffix = f" rows={table['row_count']}"
            self.stdout.write(f"\n[{table['table_name']}]{suffix}")
            for column in table["columns"]:
                default = column["column_default"] or ""
                self.stdout.write(
                    "  - {column_name}: {data_type}, nullable={is_nullable}, default={default}".format(
                        **column, default=default
                    )
                )
