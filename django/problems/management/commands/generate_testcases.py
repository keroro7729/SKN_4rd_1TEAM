"""테스트케이스 생성 에이전트 (CLI, dry-run 또는 저장).

핵심 로직은 problems.services.testcase_agent 에 있다(실행/제출 자동생성과 공용).
  - 기본: 생성만 하고 JSON 출력(dry-run)
  - --save: problems.TestCase 로 저장(이미 있으면 skip)

실행(로컬):
  docker compose -f docker-compose.yml -f docker-compose.local.yml \
    run --rm django python manage.py generate_testcases <problem_id> [--seeds N] [--save]
"""
import json

from django.core.management.base import BaseCommand, CommandError

from problems.models import Problem
from problems.services.testcase_agent import (
    TestcaseAgentError,
    generate_and_save,
    generate_testcases,
)


class Command(BaseCommand):
    help = "문제 하나의 테스트케이스를 정답코드/생성기 기반으로 생성한다(dry-run 또는 --save)."

    def add_arguments(self, parser):
        parser.add_argument("problem_id", type=int)
        parser.add_argument("--seeds", type=int, default=100, help="랜덤 TC 개수(기본 100)")
        parser.add_argument("--timeout", type=int, default=5, help="입력당 실행 제한(초)")
        parser.add_argument("--max-fix", type=int, default=2, help="디버깅 루프 최대 횟수")
        parser.add_argument("--poll", type=int, default=180, help="워커 잡 폴링 제한(초)")
        parser.add_argument("--save", action="store_true", help="problems.TestCase 로 저장")
        parser.add_argument("--out", default="", help="결과 JSON 저장 경로(선택)")

    def handle(self, *args, **opts):
        try:
            problem = Problem.objects.get(pk=opts["problem_id"])
        except Problem.DoesNotExist:
            raise CommandError(f"problem {opts['problem_id']} 없음")

        kw = dict(
            seeds=opts["seeds"],
            timeout=opts["timeout"],
            poll=opts["poll"],
            max_fix=opts["max_fix"],
            log=lambda m: self.stdout.write(f"  {m}"),
        )
        self.stdout.write(f"[생성] problem #{problem.id} {problem.title[:40]!r}")
        try:
            if opts["save"]:
                summary = generate_and_save(problem, user=None, **kw)
                self.stdout.write(self.style.SUCCESS(f"저장 완료: {summary}"))
                return
            result = generate_testcases(problem, user=None, **kw)
        except TestcaseAgentError as exc:
            raise CommandError(str(exc))

        out = {"problem_id": problem.id, **result}
        payload_json = json.dumps(out, ensure_ascii=False, indent=2)
        if opts["out"]:
            with open(opts["out"], "w", encoding="utf-8") as f:
                f.write(payload_json)
            self.stdout.write(f"저장: {opts['out']}")
        else:
            self.stdout.write(payload_json)
