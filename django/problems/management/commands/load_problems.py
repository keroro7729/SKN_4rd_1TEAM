"""Import problem_dataset.csv into PostgreSQL with Korean service titles.

개선(로드 과정):
- 제목: 설명의 **온점(.) 기준 첫 문장** + 길이 제한(--max-title, 기본 50) → 짧은 제목.
- 알고리즘 분류: 상세한 영문 태그를 **키워드 룰 기반으로 단순 캐논니컬 분류**(~14종, 한글).
- 난이도: 캐논니컬 알고리즘 기반 **룰로 자동 분류**(basic/beginner/intermediate/advanced).

The command writes to the database currently connected through Django settings.
Use --target to make local/RDS intent explicit and prevent accidental seeding.
"""
from __future__ import annotations

import csv
import json
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils.text import slugify

from problems.models import Problem, ProblemCategory, ProblemChecker, ProblemTag

DEFAULT_CSV = "/app/data/django/seed/problem_dataset.csv"
DEFAULT_MAX_TITLE = 50

MENU_CATEGORIES = {
    "data-structures": "자료구조",
    "algorithms": "알고리즘",
}

DATA_STRUCTURE_TAGS = {
    "array", "string", "hash map", "hash set", "set", "stack", "queue",
    "priority queue", "heap", "deque", "tree", "binary tree", "segment tree",
    "fenwick tree", "trie", "linked list", "graph", "grid", "disjoint set",
    "union find",
}

VALID_DIFFICULTIES = {"basic", "beginner", "intermediate", "advanced"}
LOCAL_DB_HOSTS = {"", "postgres", "localhost", "127.0.0.1", "host.docker.internal"}

# 상세 영문 알고리즘 → 단순 캐논니컬 분류 (앞 규칙 우선, 키워드 부분일치)
ALGO_CANON_RULES = [
    (("dynamic", "dp", "memoiz", "knapsack"), "동적계획법"),
    (("dijkstra", "bellman", "floyd", "shortest", "spanning", "mst", "topolog",
      "union", "disjoint", "scc", "dfs", "bfs", "graph", "tree", "trie", "traversal"), "그래프/탐색"),
    (("binary search", "ternary", "parametric"), "이분탐색"),
    (("two pointer", "sliding window"), "투포인터"),
    (("greedy",), "그리디"),
    (("sort",), "정렬"),
    (("hash", "map", "dictionary", "set"), "해시"),
    (("stack", "queue", "deque", "heap", "priority"), "자료구조"),
    (("string", "kmp", "suffix", "palindrome", "regex", "parsing"), "문자열"),
    (("math", "number theory", "prime", "gcd", "lcm", "modul", "combinat",
      "arithmetic", "geometr", "probab", "factorial"), "수학"),
    (("bit", "xor", "mask"), "비트마스크"),
    (("backtrack", "permutation", "combination", "brute", "recursion"), "완전탐색"),
    (("simulation", "implementation", "ad hoc"), "구현"),
    (("prefix", "suffix", "array", "linear scan", "subarray"), "배열"),
]

# 캐논니컬 분류별 난이도 가중치 (높을수록 어려움)
CANON_WEIGHT = {
    "배열": 1, "수학": 1, "구현": 1, "문자열": 1, "정렬": 1,
    "완전탐색": 2, "그리디": 2, "해시": 2, "자료구조": 2, "투포인터": 2,
    "비트마스크": 2, "이분탐색": 2,
    "그래프/탐색": 3, "동적계획법": 3,
}


class Command(BaseCommand):
    help = "Import problem_dataset.csv into PostgreSQL Problem tables (룰기반 제목·분류·난이도)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", nargs="?", default=DEFAULT_CSV)
        parser.add_argument("--reset", action="store_true", help="Delete existing problems before import.")
        parser.add_argument("--difficulty", default="auto", help="auto=알고리즘 룰 기반, 또는 basic/beginner/intermediate/advanced 고정.")
        parser.add_argument("--max-title", type=int, default=DEFAULT_MAX_TITLE, help="제목 최대 길이(기본 50).")
        parser.add_argument("--keep-existing-categories", action="store_true")
        parser.add_argument(
            "--target", choices=("auto", "local", "rds"), default="auto",
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

    def _canon_algos(self, algos: list[str]) -> list[str]:
        """상세 영문 알고리즘 → 단순 캐논니컬 분류 목록(중복 제거, 등장 순서 유지)."""
        cats: list[str] = []
        for algo in algos:
            lowered = algo.lower()
            for keywords, label in ALGO_CANON_RULES:
                if any(keyword in lowered for keyword in keywords):
                    if label not in cats:
                        cats.append(label)
                    break
        return cats

    def _menu_category_slug(self, algos: list[str]) -> str:
        normalized = {algo.strip().lower() for algo in algos}
        return "data-structures" if normalized & DATA_STRUCTURE_TAGS else "algorithms"

    def _auto_difficulty(self, canon: list[str]) -> str:
        """캐논니컬 알고리즘 기반 난이도. 최대 가중치가 주(主), 개수는 보조 가점."""
        if not canon:
            return "basic"
        max_weight = max(CANON_WEIGHT.get(cat, 1) for cat in canon)
        n = len(canon)
        if max_weight >= 3:            # 그래프/DP 등 고난도 계열
            return "advanced" if n >= 2 else "intermediate"
        if max_weight == 2:            # 중간 계열
            if n >= 3:
                return "advanced"
            return "intermediate" if n >= 2 else "beginner"
        return "beginner" if n >= 2 else "basic"  # 단순 계열

    def _difficulty(self, option: str, canon: list[str]) -> str:
        if option != "auto":
            return option if option in VALID_DIFFICULTIES else "beginner"
        return self._auto_difficulty(canon)

    def _make_title(self, description: str, index: int, max_len: int) -> str:
        """설명의 온점(.) 기준 첫 문장 + 길이 제한."""
        text = re.sub(r"\s+", " ", (description or "").strip())
        if not text:
            return f"문제 {index:03d}"
        # 문장 종결(. ? ! 。) + 공백 기준 첫 문장
        first = re.split(r"(?<=[.?!。])\s+", text, maxsplit=1)[0].strip()
        first = first.rstrip(".?!。").strip(" #*-:;,()[]{}\"'")
        # 첫 문장이 너무 짧으면(예: "예.") 전체 텍스트에서 확보
        if len(first) < 6:
            first = text.strip(" #*-:;,()[]{}\"'")
        if len(first) > max_len:  # '…' 포함 총 길이가 max_len 을 넘지 않게
            first = first[:max_len - 1].rstrip() + "…"
        return first or f"문제 {index:03d}"

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
        max_title = options["max_title"]

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

                algos_raw = self._parse_algos(row.get("algorithm_selection"))
                canon = self._canon_algos(algos_raw)
                category = self._get_category(self._menu_category_slug(algos_raw))
                difficulty = self._difficulty(options["difficulty"], canon)
                title = self._make_title(description, index, max_title)

                problem, is_new = Problem.objects.get_or_create(
                    description=description,
                    defaults={"title": title, "category": category, "difficulty": difficulty, "is_active": True},
                )
                tag_objects = [self._get_tag(cat) for cat in canon]
                problem.tags.set(tag_objects)
                ProblemChecker.objects.get_or_create(problem=problem)

                changed_fields = []
                for field, value in (("title", title), ("category", category), ("difficulty", difficulty), ("is_active", True)):
                    if getattr(problem, field) != value:
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
