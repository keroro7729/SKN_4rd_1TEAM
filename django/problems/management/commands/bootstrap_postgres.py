"""Bootstrap PostgreSQL schema and seed data for local or RDS deployment."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import CommandError, call_command
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from gamification.models import Mission
from notices.models import Notice
from problems.models import Problem, ProblemCategory, ProblemTag, TestCase

DEFAULT_CSV = "/app/data/django/seed/problem_dataset.csv"
LOCAL_DB_HOSTS = {"", "postgres", "localhost", "127.0.0.1", "host.docker.internal"}


@dataclass(frozen=True)
class SeedResult:
    name: str
    count: int


class Command(BaseCommand):
    help = "Initialize the connected PostgreSQL database with schema and seed data."

    def add_arguments(self, parser):
        parser.add_argument("--skip-migrate", action="store_true")
        parser.add_argument("--problem-csv", default=DEFAULT_CSV)
        parser.add_argument("--difficulty", default="auto")
        parser.add_argument("--no-sync-problems", action="store_true")
        parser.add_argument("--no-seed-base-data", action="store_true")
        parser.add_argument("--seed-smoke-testcase", action="store_true")
        parser.add_argument("--require-rds", action="store_true")
        parser.add_argument("--target", choices=("auto", "local", "rds"), default="auto")
        parser.add_argument("--print-tables", action="store_true")

    def handle(self, *args, **options):
        target = self._validate_database(options["require_rds"], options["target"])

        if not options["skip_migrate"]:
            self.stdout.write("Applying migrations...")
            call_command("migrate", interactive=False, verbosity=1)

        missing_tables = self._missing_managed_tables()
        if missing_tables:
            raise CommandError("Missing PostgreSQL tables after migration: " + ", ".join(missing_tables))

        results: list[SeedResult] = []
        if not options["no_seed_base_data"]:
            results.extend(self._seed_base_data())

        if not options["no_sync_problems"]:
            csv_path = Path(options["problem_csv"])
            if not csv_path.exists():
                raise CommandError(f"Problem CSV not found: {csv_path}")
            before = Problem.objects.count()
            call_command("load_problems", str(csv_path), difficulty=options["difficulty"], target=target, verbosity=1)
            results.append(SeedResult("problems_imported_or_existing", Problem.objects.count() - before))

        if options["seed_smoke_testcase"]:
            results.append(self._seed_smoke_testcase())

        self._print_summary(results, print_tables=options["print_tables"])

    def _db_kind(self) -> str:
        host = (settings.DATABASES["default"].get("HOST") or "").strip().lower()
        return "local" if host in LOCAL_DB_HOSTS else "rds"

    def _validate_database(self, require_rds: bool, target: str) -> str:
        if connection.vendor != "postgresql":
            raise CommandError(f"PostgreSQL is required, current vendor={connection.vendor}")
        actual = self._db_kind()
        host = settings.DATABASES["default"].get("HOST", "")
        if require_rds and actual != "rds":
            raise CommandError("POSTGRES_HOST must point to the RDS endpoint when --require-rds is used.")
        if target != "auto" and target != actual:
            raise CommandError(f"Target mismatch: requested={target}, connected={actual}, host={host}")
        self.stdout.write(f"Database vendor: {connection.vendor}")
        self.stdout.write(f"Database host: {host}")
        self.stdout.write(f"Database target: {actual}")
        return actual

    def _missing_managed_tables(self) -> list[str]:
        existing = set(connection.introspection.table_names())
        expected = {
            model._meta.db_table
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy
        }
        return sorted(expected - existing)

    @transaction.atomic
    def _seed_base_data(self) -> list[SeedResult]:
        mission_specs = [
            ("오늘 문제 1개 풀기", "submission_created", 1, 30),
            ("오답노트 1개 작성하기", "wrongnote_completed", 1, 30),
            ("복습 1개 완료하기", "review_completed", 1, 30),
        ]
        mission_created = 0
        for title, trigger_action, target_count, reward_point in mission_specs:
            _, created = Mission.objects.update_or_create(
                title=title,
                defaults={
                    "trigger_action": trigger_action,
                    "target_count": target_count,
                    "reward_point": reward_point,
                    "is_active": True,
                },
            )
            mission_created += int(created)

        _, notice_created = Notice.objects.get_or_create(
            title="WOOK'S CODING 서비스 안내",
            defaults={
                "content": "문제 풀이, 코드 실행, 오답노트 기능을 순차적으로 제공합니다.",
                "is_published": True,
            },
        )
        return [SeedResult("missions_created", mission_created), SeedResult("notices_created", int(notice_created))]

    @transaction.atomic
    def _seed_smoke_testcase(self) -> SeedResult:
        category, _ = ProblemCategory.objects.get_or_create(
            slug="operational-check",
            defaults={"name": "운영점검", "order": 999, "is_active": True},
        )
        tag, _ = ProblemTag.objects.get_or_create(slug="smoke-test", defaults={"name": "Smoke Test"})
        problem, _ = Problem.objects.get_or_create(
            title="운영 점검용 두 수 합",
            defaults={
                "category": category,
                "description": "두 정수 A와 B를 입력받아 합을 출력하라.",
                "difficulty": "basic",
                "constraints": "운영 점검용 문제입니다.",
                "is_active": True,
            },
        )
        problem.tags.add(tag)

        created = 0
        cases = [("1 2\n", "3\n"), ("10 -3\n", "7\n"), ("0 0\n", "0\n")]
        for input_data, expected_output in cases:
            _, is_created = TestCase.objects.get_or_create(
                problem=problem,
                input_data=input_data,
                expected_output=expected_output,
                defaults={"is_sample": True, "compare_mode": "line_trim"},
            )
            created += int(is_created)
        return SeedResult("smoke_testcases_created", created)

    def _print_summary(self, results: list[SeedResult], print_tables: bool) -> None:
        table_names = sorted(connection.introspection.table_names())
        counts = {
            "ProblemCategory": ProblemCategory.objects.count(),
            "ProblemTag": ProblemTag.objects.count(),
            "Problem": Problem.objects.count(),
            "TestCase": TestCase.objects.count(),
            "Mission": Mission.objects.count(),
            "Notice": Notice.objects.count(),
        }
        for result in results:
            self.stdout.write(f"{result.name}: {result.count}")
        self.stdout.write("PostgreSQL table count: " + str(len(table_names)))
        if print_tables:
            self.stdout.write("PostgreSQL tables:")
            for table_name in table_names:
                self.stdout.write(f"- {table_name}")
        for name, count in counts.items():
            self.stdout.write(f"{name}: {count}")
        self.stdout.write(self.style.SUCCESS("PostgreSQL bootstrap complete."))