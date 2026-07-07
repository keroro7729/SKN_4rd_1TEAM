"""테스트케이스 생성 에이전트 (dry-run).

흐름:
  1) FastAPI(LLM)로 정답코드 + 랜덤 생성기 + 엣지/시간 입력 생성
  2) Worker(code_eval)에 생성기를 위임해 seed 0..N-1 로 랜덤 small 입력 N개 확보
  3) Worker(code_eval)에 정답코드를 위임해 (엣지+시간+랜덤) 입력의 기대출력/실행시간 산출
  4) 크래시 시 FastAPI fix 로 디버깅 루프(최대 --max-fix 회)
  5) 최종 TC 리스트(random/edge/time) 반환 — DB 저장 없음(dry-run)

실행(로컬):
  docker compose -f docker-compose.yml -f docker-compose.local.yml \
    run --rm django python manage.py generate_testcases <problem_id>
"""
import json
import time

from django.core.management.base import BaseCommand, CommandError

from ai_proxy.client import FastAPIClientError, call_fastapi
from problems.models import Problem
from submissions.models import ExecutionJob

TERMINAL = {"success", "failed", "timeout"}


class Command(BaseCommand):
    help = "문제 하나에 대해 정답코드/생성기 기반 테스트케이스를 생성한다(dry-run)."

    def add_arguments(self, parser):
        parser.add_argument("problem_id", type=int)
        parser.add_argument("--seeds", type=int, default=100, help="랜덤 TC 개수(기본 100)")
        parser.add_argument("--timeout", type=int, default=5, help="입력당 실행 제한(초)")
        parser.add_argument("--max-fix", type=int, default=2, help="디버깅 루프 최대 횟수")
        parser.add_argument("--poll", type=int, default=180, help="워커 잡 폴링 제한(초)")
        parser.add_argument("--out", default="", help="결과 JSON 저장 경로(선택)")

    # --- Worker(code_eval) 위임 ---
    def _eval_batch(self, code, inputs, timeout, poll_timeout):
        job = ExecutionJob.objects.create(
            job_type="code_eval",
            status="pending",
            input_payload={"code": code, "inputs": inputs, "timeout": timeout},
        )
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            time.sleep(1)
            job.refresh_from_db(fields=["status", "result_payload"])
            if job.status in TERMINAL:
                break
        else:
            raise CommandError(f"eval job {job.id} 폴링 타임아웃({poll_timeout}s)")
        if job.status != "success":
            msg = (job.result_payload or {}).get("error_message", "")
            raise CommandError(f"eval job {job.id} 실패: {msg}")
        return (job.result_payload or {}).get("results", [])

    def _call(self, request_type, path, payload):
        try:
            res = call_fastapi(
                user=None,
                request_type=request_type,
                path=path,
                payload=payload,
                timeout=120,
                raise_on_error=True,
            )
        except FastAPIClientError as exc:
            raise CommandError(f"FastAPI {path} 실패: {exc.result.message}") from exc
        return res.data

    # --- 정답코드 실행 + 디버깅 루프 ---
    def _run_solution(self, base_payload, solution, cand, timeout, poll_timeout, max_fix):
        inputs = [inp for _, inp in cand]
        results = []
        for attempt in range(max_fix + 1):
            results = self._eval_batch(solution, inputs, timeout, poll_timeout)
            crash = None
            for i, r in enumerate(results):
                if not r["timed_out"] and r["returncode"] not in (0, None):
                    crash = (i, r)
                    break
            if crash is None:
                return solution, results
            if attempt == max_fix:
                self.stdout.write(
                    self.style.WARNING(f"  디버깅 {max_fix}회 후에도 크래시 잔존 — 해당 케이스 제외")
                )
                return solution, results
            i, r = crash
            self.stdout.write(f"  디버깅 루프 {attempt + 1}: 케이스#{i} 크래시 → fix 요청")
            data = self._call(
                "testcase_fix",
                "/ai/authoring/fix",
                {
                    **base_payload,
                    "solution_code": solution,
                    "error": (r["stderr"] or "")[:1500],
                    "sample_input": cand[i][1][:1000],
                },
            )
            solution = data["solution_code"]
        return solution, results

    def handle(self, *args, **opts):
        try:
            problem = Problem.objects.get(pk=opts["problem_id"])
        except Problem.DoesNotExist:
            raise CommandError(f"problem {opts['problem_id']} 없음")

        timeout, poll = opts["timeout"], opts["poll"]
        base_payload = {
            "problem_id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "constraints": problem.constraints,
        }

        # 1) 생성 (LLM)
        self.stdout.write(f"[1/4] 생성 요청: problem #{problem.id} {problem.title[:40]!r}")
        gen = self._call("testcase_gen", "/ai/authoring/generate", base_payload)
        solution = gen["solution_code"]
        generator = gen["generator_code"]
        edge_inputs = gen.get("edge_inputs", [])
        time_inputs = gen.get("time_inputs", [])
        self.stdout.write(
            f"  solution {len(solution)}B · generator {len(generator)}B · "
            f"edge {len(edge_inputs)} · time {len(time_inputs)}"
        )

        # 2) 생성기 → 랜덤 입력 N개 (Worker)
        self.stdout.write(f"[2/4] 랜덤 입력 생성(seed 0..{opts['seeds'] - 1})")
        seeds = [str(i) for i in range(opts["seeds"])]
        gen_results = self._eval_batch(generator, seeds, timeout, poll)
        random_inputs = [
            r["stdout"]
            for r in gen_results
            if r["returncode"] == 0 and not r["timed_out"] and r["stdout"].strip()
        ]
        self.stdout.write(f"  랜덤 입력 {len(random_inputs)}/{len(seeds)}개 확보")

        # 3) 정답코드 실행(엣지+시간+랜덤) + 디버깅 루프
        cand = (
            [("edge", s) for s in edge_inputs]
            + [("time", s) for s in time_inputs]
            + [("random", s) for s in random_inputs]
        )
        self.stdout.write(f"[3/4] 정답코드로 기대출력 산출({len(cand)}건) + 디버깅 루프")
        solution, sol_results = self._run_solution(
            base_payload, solution, cand, timeout, poll, opts["max_fix"]
        )

        # 4) 최종 TC 조립 (성공 케이스만)
        final = []
        for (kind, inp), r in zip(cand, sol_results):
            if r["returncode"] == 0 and not r["timed_out"]:
                final.append(
                    {
                        "kind": kind,
                        "input": inp,
                        "expected_output": r["stdout"],
                        "elapsed_ms": r["elapsed_ms"],
                        "compare_mode": "line_trim",
                    }
                )
        counts = {
            "random": sum(1 for t in final if t["kind"] == "random"),
            "edge": sum(1 for t in final if t["kind"] == "edge"),
            "time": sum(1 for t in final if t["kind"] == "time"),
            "total": len(final),
        }
        self.stdout.write(self.style.SUCCESS(f"[4/4] 최종 TC {counts}"))

        result = {"problem_id": problem.id, "counts": counts, "test_cases": final}
        payload_json = json.dumps(result, ensure_ascii=False, indent=2)
        if opts["out"]:
            with open(opts["out"], "w", encoding="utf-8") as f:
                f.write(payload_json)
            self.stdout.write(f"저장: {opts['out']}")
        else:
            self.stdout.write(payload_json)
