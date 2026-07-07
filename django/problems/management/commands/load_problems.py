"""Import problem_dataset.csv into PostgreSQL with Korean service titles.

The command writes to the database currently connected through Django settings.
Use --target to make local/RDS intent explicit and prevent accidental seeding.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils.text import slugify

from problems.models import Problem, ProblemCategory, ProblemChecker, ProblemTag

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
LOCAL_DB_HOSTS = {"", "postgres", "localhost", "127.0.0.1", "host.docker.internal"}

ALGORITHM_TITLE_MAP = [
    ({"arithmetic", "mathematical formula", "64-bit integer arithmetic", "big integer arithmetic"}, "사칙연산"),
    ({"topological sort", "topological sorting"}, "위상정렬"),
    ({"tree", "binary tree", "segment tree", "fenwick tree", "trie"}, "Tree"),
    ({"array", "prefix maxima", "suffix maxima", "two pointers", "prefix sum"}, "배열"),
    ({"hash map", "hash set", "hashing"}, "해싱"),
    ({"dynamic programming", "bitmask", "unbounded knapsack"}, "DP"),
    ({"backtracking", "dfs", "bruteforce", "brute force"}, "백트래킹"),
]

CONTENT_TITLE_RULES = [
    (("gold", "mine"), "금 채굴하기"),
    (("금", "채굴"), "금 채굴하기"),
    (("tilted", "square"), "기울어진 사각형"),
    (("rotated", "rectangle"), "기울어진 사각형"),
    (("기울어진", "사각"), "기울어진 사각형"),
    (("pizza",), "피자 나누기"),
    (("피자",), "피자 나누기"),
    (("chess",), "체스판 배치"),
    (("체스",), "체스판 배치"),
    (("tetris",), "테트리스 필드 비우기"),
    (("median",), "배열 중앙값 맞추기"),
    (("stove", "chicken"), "자동 꺼짐 스토브"),
    (("card", "pile"), "카드 더미 이동"),
    (("message", "friends"), "친구 관계 찾기"),
    (("coin", "flip"), "동전 뒤집기"),
    (("p*a", "q*a", "r*a"), "배열 수식 최댓값"),
    (("100", "101", "102", "103", "104", "105"), "상품 금액 만들기"),
    (("three distinct", "sum"), "세 수의 합"),
    (("hydra",), "히드라 그래프 찾기"),
    (("reverse", "segment", "increasing"), "구간 뒤집어 정렬하기"),
    (("beer", "i^3"), "맥주값 계산하기"),
    (("shortest path",), "최단 경로 찾기"),
    (("palindrome",), "팰린드롬 판별"),
    (("parentheses",), "괄호 문자열 처리"),
    (("substring",), "부분 문자열 처리"),
]

ALGORITHM_FALLBACKS = {
    "사칙연산": "사칙연산 계산 문제",
    "위상정렬": "위상정렬 순서 찾기",
    "Tree": "Tree 구조 탐색",
    "배열": "배열 처리",
    "해싱": "해싱 기반 조회",
    "DP": "DP 최적화",
    "백트래킹": "백트래킹 탐색",
}


@dataclass(frozen=True)
class TitleContext:
    row: dict
    index: int
    description: str
    algorithms: list[str]
    difficulty: str


class Command(BaseCommand):
    help = "Import problem_dataset.csv into PostgreSQL Problem tables."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", nargs="?", default=DEFAULT_CSV)
        parser.add_argument("--reset", action="store_true", help="Delete existing problems before import.")
        parser.add_argument("--difficulty", default="auto")
        parser.add_argument("--keep-existing-categories", action="store_true")
        parser.add_argument(
            "--target",
            choices=("auto", "local", "rds"),
            default="auto",
            help="Validate whether the connected DB is local/docker or RDS before import.",
        )

    def _db_kind(self) -> str:
        host = (settings.DATABASES["default"].get("HOST") or "").strip().lower()
        return "local" if host in LOCAL_DB_HOSTS else "rds"

    def _validate_target(self, target: str) -> None:
        if connection.vendor != "postgresql":
            raise CommandError(f"PostgreSQL is required, current vendor={connection.vendor}")
        actual = self._db_kind()
        host = settings.DATABASES["default"].get("HOST") or ""
        if target != "auto" and target != actual:
            raise CommandError(f"Target mismatch: requested={target}, connected={actual}, host={host}")
        self.stdout.write(f"Problem import target={actual}, host={host}")

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
        return [part.strip() for part in raw.split(",") if part.strip()] or [raw]

    def _menu_category_slug(self, algos: list[str]) -> str:
        normalized = {algo.strip().lower() for algo in algos}
        return "data-structures" if normalized & DATA_STRUCTURE_TAGS else "algorithms"

    def _difficulty(self, row: dict, option: str) -> str:
        if option != "auto":
            return option if option in VALID_DIFFICULTIES else "beginner"
        source_file = (row.get("source_file") or "").strip()
        return SOURCE_DIFFICULTY_MAP.get(source_file, "beginner")

    def _algorithm_label(self, algos: list[str]) -> str:
        normalized = {algo.strip().lower() for algo in algos}
        for candidates, label in ALGORITHM_TITLE_MAP:
            if normalized & candidates:
                return label
        return "알고리즘"

    def _title(self, context: TitleContext) -> str:
        text = self._source_text(context).lower()
        algorithm_label = self._algorithm_label(context.algorithms)

        for keywords, title in CONTENT_TITLE_RULES:
            if all(keyword.lower() in text for keyword in keywords):
                return self._decorate_title(title, algorithm_label)

        explicit_title = self._explicit_title(context.row)
        if explicit_title:
            return self._decorate_title(explicit_title, algorithm_label)

        fallback = ALGORITHM_FALLBACKS.get(algorithm_label, "알고리즘 문제")
        return f"{fallback} {context.index:03d}"

    def _decorate_title(self, title: str, algorithm_label: str) -> str:
        clean = self._clean_title(title)
        if algorithm_label in {"알고리즘", "배열"}:
            return clean
        if clean.startswith(algorithm_label):
            return clean
        return f"{algorithm_label}: {clean}"[:80]

    def _source_text(self, context: TitleContext) -> str:
        return " ".join(
            [
                context.row.get("question") or "",
                context.row.get("problem_korean") or "",
                context.row.get("problem_understanding") or "",
                context.row.get("selection_reason") or "",
                context.row.get("implementation_plan") or "",
                " ".join(context.algorithms),
                context.description,
            ]
        )

    def _explicit_title(self, row: dict) -> str:
        question = (row.get("question") or "").strip()
        first_line = question.splitlines()[0].strip() if question else ""
        if not first_line or len(first_line) > 80:
            return ""
        lowered = first_line.lower()
        reject_markers = (
            "example",
            "sample",
            "input",
            "output",
            "note",
            "you are given",
            "given ",
            "there are",
            "calculate",
            "determine",
            "find ",
            "print ",
        )
        if any(marker in lowered for marker in reject_markers):
            return ""
        match = re.match(r"^(?:problem\s+[a-z0-9]+|[a-z0-9]+)\s*[:.\-]\s*(.{4,80})$", first_line, flags=re.IGNORECASE)
        title = self._clean_title(match.group(1) if match else first_line)
        return title if re.search(r"[가-힣]", title) else ""

    def _clean_title(self, text: str) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip())
        text = text.strip(" #*-:;,.()[]{}\"")
        return text[:80]

    def _get_category(self, slug: str) -> ProblemCategory:
        category, _ = ProblemCategory.objects.get_or_create(
            slug=slug,
            defaults={"name": MENU_CATEGORIES[slug], "order": 10 if slug == "data-structures" else 20, "is_active": True},
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
        tag, _ = ProblemTag.objects.get_or_create(slug=self._slug(name), defaults={"name": name[:50]})
        if tag.name != name[:50]:
            tag.name = name[:50]
            tag.save(update_fields=["name"])
        return tag

    @transaction.atomic
    def handle(self, *args, **options):
        self._validate_target(options["target"])
        csv_path = options["csv_path"]

        try:
            csv_file = open(csv_path, encoding="utf-8-sig", newline="")
        except FileNotFoundError as exc:
            raise CommandError(f"CSV file not found: {csv_path}") from exc

        if options["reset"]:
            count = Problem.objects.count()
            Problem.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted existing Problem rows: {count}"))

        created = updated = skipped = 0
        with csv_file:
            reader = csv.DictReader(csv_file)
            required = {"problem_korean", "algorithm_selection"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise CommandError(f"Missing required columns. required={required}, found={reader.fieldnames}")

            for index, row in enumerate(reader, start=1):
                description = (row.get("problem_korean") or "").strip()
                if not description:
                    skipped += 1
                    continue

                algos = self._parse_algos(row.get("algorithm_selection"))
                category = self._get_category(self._menu_category_slug(algos))
                difficulty = self._difficulty(row, options["difficulty"])
                title = self._title(TitleContext(row, index, description, algos, difficulty))

                problem, is_new = Problem.objects.get_or_create(
                    description=description,
                    defaults={"title": title, "category": category, "difficulty": difficulty, "is_active": True},
                )
                tag_objects = [self._get_tag(algo) for algo in algos]
                if tag_objects:
                    problem.tags.set(tag_objects)
                ProblemChecker.objects.get_or_create(problem=problem)

                changed_fields = []
                for field, value in (("title", title), ("category", category), ("difficulty", difficulty), ("is_active", True)):
                    current = getattr(problem, field)
                    if current != value:
                        setattr(problem, field, value)
                        changed_fields.append(field)
                if changed_fields:
                    problem.save(update_fields=changed_fields)

                if is_new:
                    created += 1
                elif changed_fields:
                    updated += 1
                else:
                    skipped += 1

        if not options["keep_existing_categories"]:
            ProblemCategory.objects.exclude(slug__in=MENU_CATEGORIES.keys()).update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                "Complete. "
                f"created={created}, updated={updated}, skipped={skipped}, "
                f"categories={ProblemCategory.objects.filter(is_active=True).count()}, "
                f"tags={ProblemTag.objects.count()}, problems={Problem.objects.count()}, checkers={ProblemChecker.objects.count()}"
            )
        )