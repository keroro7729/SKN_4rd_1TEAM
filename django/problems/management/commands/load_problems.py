"""문제 데이터셋(CSV) 적재 관리 명령 (dev seed).

CSV 컬럼: question, problem_korean, problem_understanding, algorithm_selection,
          selection_reason, implementation_plan, source_file
이 중 problem_korean, algorithm_selection 만 사용한다.
  - problem_korean      -> Problem.description (+ 첫 줄에서 title 파생)
  - algorithm_selection -> JSON 배열(예: ["Greedy","Math"]) 로 파싱해
                           · 각 원소 -> ProblemTag (M2M)
                           · 첫 원소 -> ProblemCategory (필수 FK, 대표 알고리즘). 빈 배열이면 "기타".

Django ORM 을 사용하므로 컨테이너 내부에서 실행한다(권장):
  docker compose run --build --rm django python manage.py load_problems
  docker compose run --rm django python manage.py load_problems --reset

멱등성: 같은 problem_korean(description) 이 이미 있으면 건너뛴다. 전체 재적재는 --reset.
"""
import csv
import json

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from problems.models import Problem, ProblemCategory, ProblemTag

# 컨테이너에 마운트되는 기본 경로 (docker-compose: ./volumes/data:/app/data:ro)
DEFAULT_CSV = "/app/data/django/seed/problem_dataset.csv"


class Command(BaseCommand):
    help = "problem_dataset.csv 적재 (problem_korean, algorithm_selection 사용)"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path", nargs="?", default=DEFAULT_CSV, help=f"CSV 경로 (기본 {DEFAULT_CSV})"
        )
        parser.add_argument(
            "--reset", action="store_true", help="적재 전 기존 Problem 전체 삭제"
        )
        parser.add_argument(
            "--difficulty", default="beginner", help="일괄 난이도 (기본 beginner)"
        )

    def _slug(self, name: str) -> str:
        # 알고리즘명이 한글일 수도 있어 allow_unicode=True, SlugField(50) 대비 절단
        return slugify(name, allow_unicode=True)[:50] or "etc"

    def _parse_algos(self, raw: str) -> list:
        """algorithm_selection 셀을 알고리즘명 리스트로 파싱한다.

        기대 형식: '["Greedy", "Math"]'. 파싱 실패 시 원문을 단일 태그로 취급.
        """
        raw = (raw or "").strip()
        if not raw:
            return []
        try:
            v = json.loads(raw)
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return [raw]

    def _get_tag(self, name: str) -> ProblemTag:
        tag, _ = ProblemTag.objects.get_or_create(
            slug=self._slug(name), defaults={"name": name[:50]}
        )
        return tag

    @transaction.atomic
    def handle(self, *args, **opts):
        csv_path = opts["csv_path"]

        try:
            f = open(csv_path, encoding="utf-8-sig", newline="")
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"CSV 파일 없음: {csv_path}"))
            self.stderr.write(
                "  컨테이너에 마운트됐는지 확인: django 서비스의 "
                "'./volumes/data:/app/data:ro' 볼륨."
            )
            return

        if opts["reset"]:
            n = Problem.objects.count()
            Problem.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"기존 Problem {n}건 삭제"))

        created = skipped = 0
        with f:
            reader = csv.DictReader(f)
            need = {"problem_korean", "algorithm_selection"}
            if not need.issubset(set(reader.fieldnames or [])):
                self.stderr.write(
                    self.style.ERROR(
                        f"필수 컬럼 누락 (필요 {need}, 발견 {reader.fieldnames})"
                    )
                )
                return

            for i, row in enumerate(reader, start=1):
                desc = (row.get("problem_korean") or "").strip()
                if not desc:
                    skipped += 1
                    continue

                algos = self._parse_algos(row.get("algorithm_selection"))
                primary = algos[0] if algos else "기타"
                title = (desc.splitlines()[0].strip() or f"문제 {i}")[:200]

                category, _ = ProblemCategory.objects.get_or_create(
                    slug=self._slug(primary), defaults={"name": primary[:50]}
                )

                problem, is_new = Problem.objects.get_or_create(
                    description=desc,
                    defaults={
                        "title": title,
                        "category": category,
                        "difficulty": opts["difficulty"],
                        "is_active": True,
                    },
                )
                if is_new:
                    problem.tags.add(*[self._get_tag(a) for a in algos])
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료 · 신규 {created} · 스킵(중복/빈값) {skipped} · "
                f"카테고리 {ProblemCategory.objects.count()} · "
                f"태그 {ProblemTag.objects.count()} · "
                f"전체 문제 {Problem.objects.count()}"
            )
        )
