"""Inspect VectorDB state through the internal FastAPI diagnostics endpoint."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from ._vector_helpers import call_vector_diagnostics


class Command(BaseCommand):
    help = "Inspect ChromaDB through FastAPI /ai/diagnostics/chroma."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        result = call_vector_diagnostics()
        payload = {
            "ok": result.ok,
            "status": result.status,
            "request_id": result.request_id,
            "message": result.message,
            "http_status": result.http_status,
            "data": result.data,
        }
        if options["as_json"]:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write("VectorDB")
        self.stdout.write(f"- status: {result.status}")
        self.stdout.write(f"- request_id: {result.request_id}")
        if result.http_status:
            self.stdout.write(f"- http_status: {result.http_status}")
        if result.message:
            self.stdout.write(f"- message: {result.message}")

        data = result.data or {}
        required = data.get("required") or {}
        self.stdout.write("")
        self.stdout.write("Required collection")
        self.stdout.write(f"- name: {required.get('name', 'wrong_note_embeddings')}")
        self.stdout.write(f"- exists: {required.get('exists', False)}")

        self.stdout.write("")
        self.stdout.write("Collections")
        for collection in data.get("collections", []):
            self.stdout.write(
                f"- {collection.get('name')}: count={collection.get('count')}"
            )

        self.stdout.write("")
        self.stdout.write("Forbidden collections")
        for name, state in (data.get("forbidden") or {}).items():
            self.stdout.write(
                f"- {name}: exists={state.get('exists')} count={state.get('count')}"
            )

        samples = required.get("sample_metadatas") or []
        if samples:
            self.stdout.write("")
            self.stdout.write("Sample metadata")
            for item in samples:
                self.stdout.write(f"- {json.dumps(item, ensure_ascii=False)}")
