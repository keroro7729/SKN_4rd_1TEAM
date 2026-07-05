"""Import problem_dataset.csv into PostgreSQL.

The CSV is only a seed source. The application reads problems from PostgreSQL.

Expected columns:
- question
- problem_korean
- problem_understanding
- algorithm_selection
- selection_reason
- implementation_plan
- source_file
"""

from __future__ import annotations

import csv
import json

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from problems.models import Problem, ProblemCategory, ProblemTag

DEFAULT_CSV = "/app/data/django/seed/problem_dataset.csv"

MENU_CATEGORIES = {
    "data-structures": "자료구조",
    "algorithms": "알고리즘",
}

DATA_STRUCTURE_TAGS = {
    "array",
    "string",
    "hash map",
    "hash set",
    "set",
    "stack",
    "queue",
    "priority queue",
    "heap",
    "deque",
    "tree",
    "binary tree",
    "segment tree",
    "fenwick tree",
    "trie",
    "linked list",
    "graph",
    "grid",
    "disjoint set",
    "union find",
}

SOURCE_DIFFICULTY_MAP = {
    "5mini_sample.csv": "beginner",
    "add.csv": "beginner",
    "add1.csv": "beginner",
    "algorithm_dataset.csv": "intermediate",
    "algorithm_dataset_100.csv": "intermediate",
    "algorithm_dataset_300.csv": "advanced",
    "last.csv": "advanced",
    "gpt5.csv": "advanced",
}

VALID_DIFFICULTIES = {"basic", "beginner", "intermediate", "advanced"}


class Command(BaseCommand):
    help = "Import problem_dataset.csv into PostgreSQL Problem tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            nargs="?",
            default=DEFAULT_CSV,
            help=f"CSV path. Default: {DEFAULT_CSV}",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing problems before import.",
        )
        parser.add_argument(
            "--difficulty",
            default="auto",
            help="Difficulty to use. Use 'auto' to infer from source_file.",
        )
        parser.add_argument(
            "--keep-existing-categories",
            action="store_true",
            help="Keep old algorithm-name categories active.",
        )

    def _slug(self, name: str) -> str:
        return slugify(name, allow_unicode=True)[:50] or "etc"

    def _parse_algos(self, raw: str) -> list[str]:
        raw = (raw or "").strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return [raw]

    def _menu_category_slug(self, algos: list[str]) -> str:
        normalized = {algo.strip().lower() for algo in algos}
        if normalized & DATA_STRUCTURE_TAGS:
            return "data-structures"
        return "algorithms"

    def _difficulty(self, row: dict, option: str) -> str:
        if option != "auto":
            return option if option in VALID_DIFFICULTIES else "beginner"
        source_file = (row.get("source_file") or "").strip()
        return SOURCE_DIFFICULTY_MAP.get(source_file, "beginner")

    def _title(self, row: dict, index: int, description: str) -> str:
        title = (
            (row.get("question") or "").strip()
            or description.splitlines()[0].strip()
            or f"문제 {index}"
        )
        return title[:200]

    def _get_category(self, slug: str) -> ProblemCategory:
        category, _ = ProblemCategory.objects.get_or_create(
            slug=slug,
            defaults={
                "name": MENU_CATEGORIES[slug],
                "order": 10 if slug == "data-structures" else 20,
                "is_active": True,
            },
        )
        updates = {}
        if category.name != MENU_CATEGORIES[slug]:
            updates["name"] = MENU_CATEGORIES[slug]
        if not category.is_active:
            updates["is_active"] = True
        if updates:
            for field, value in updates.items():
                setattr(category, field, value)
            category.save(update_fields=list(updates))
        return category

    def _get_tag(self, name: str) -> ProblemTag:
        tag, _ = ProblemTag.objects.get_or_create(
            slug=self._slug(name),
            defaults={"name": name[:50]},
        )
        return tag

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = options["csv_path"]

        try:
            csv_file = open(csv_path, encoding="utf-8-sig", newline="")
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        if options["reset"]:
            count = Problem.objects.count()
            Problem.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted existing Problem rows: {count}"))

        created = 0
        updated = 0
        skipped = 0

        with csv_file:
            reader = csv.DictReader(csv_file)
            required = {"problem_korean", "algorithm_selection"}
            if not required.issubset(set(reader.fieldnames or [])):
                self.stderr.write(
                    self.style.ERROR(
                        f"Missing required columns. required={required}, found={reader.fieldnames}"
                    )
                )
                return

            for index, row in enumerate(reader, start=1):
                description = (row.get("problem_korean") or "").strip()
                if not description:
                    skipped += 1
                    continue

                algos = self._parse_algos(row.get("algorithm_selection"))
                category = self._get_category(self._menu_category_slug(algos))
                difficulty = self._difficulty(row, options["difficulty"])
                title = self._title(row, index, description)

                problem, is_new = Problem.objects.get_or_create(
                    description=description,
                    defaults={
                        "title": title,
                        "category": category,
                        "difficulty": difficulty,
                        "is_active": True,
                    },
                )

                tag_objects = [self._get_tag(algo) for algo in algos]
                if tag_objects:
                    problem.tags.add(*tag_objects)

                if is_new:
                    created += 1
                    continue

                changed_fields = []
                if problem.title != title:
                    problem.title = title
                    changed_fields.append("title")
                if problem.category_id != category.id:
                    problem.category = category
                    changed_fields.append("category")
                if problem.difficulty != difficulty:
                    problem.difficulty = difficulty
                    changed_fields.append("difficulty")
                if not problem.is_active:
                    problem.is_active = True
                    changed_fields.append("is_active")

                if changed_fields:
                    problem.save(update_fields=changed_fields)
                    updated += 1
                else:
                    skipped += 1

        if not options["keep_existing_categories"]:
            ProblemCategory.objects.exclude(slug__in=MENU_CATEGORIES.keys()).update(
                is_active=False
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Complete. "
                f"created={created}, updated={updated}, skipped={skipped}, "
                f"categories={ProblemCategory.objects.filter(is_active=True).count()}, "
                f"tags={ProblemTag.objects.count()}, problems={Problem.objects.count()}"
            )
        )
