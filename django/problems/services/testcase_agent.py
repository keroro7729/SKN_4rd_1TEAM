"""테스트케이스 생성 에이전트 서비스.

FastAPI(LLM) 로 정답코드·생성기·엣지/시간 입력 생성 → Worker(code_eval)로 실행 →
기대출력 산출 → 크래시 시 fix 디버깅 루프 → 최종 TC 리스트.

- `generate_testcases(problem, ...)` : TC 리스트 반환(저장 안 함, dry-run)
- `generate_and_save(problem, ...)`  : 생성 후 problems.TestCase 행으로 저장(이미 있으면 skip)

management command(generate_testcases)와 실행/제출 시 자동생성(submissions)에서 공용.
"""
import time

from ai_proxy.client import FastAPIClientError, call_fastapi

from submissions.models import ExecutionJob

_TERMINAL = {"success", "failed", "timeout"}


class TestcaseAgentError(RuntimeError):
    """생성/실행 실패."""


def _eval_batch(code, inputs, timeout, poll_timeout):
    """Worker code_eval 에 배치 위임 → results 반환."""
    job = ExecutionJob.objects.create(
        job_type="code_eval",
        status="pending",
        input_payload={"code": code, "inputs": inputs, "timeout": timeout},
    )
    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        job.refresh_from_db(fields=["status", "result_payload"])
        if job.status in _TERMINAL:
            break
    else:
        raise TestcaseAgentError(f"eval job {job.id} 폴링 타임아웃({poll_timeout}s)")
    if job.status != "success":
        raise TestcaseAgentError(
            f"eval job {job.id} 실패: {(job.result_payload or {}).get('error_message', '')}"
        )
    return (job.result_payload or {}).get("results", [])


def _call(user, request_type, path, payload):
    try:
        res = call_fastapi(
            user=user,
            request_type=request_type,
            path=path,
            payload=payload,
            timeout=120,
            raise_on_error=True,
        )
    except FastAPIClientError as exc:
        raise TestcaseAgentError(f"FastAPI {path} 실패: {exc.result.message}") from exc
    return res.data


def _run_solution(user, base_payload, solution, cand, timeout, poll, max_fix):
    """정답코드로 후보 입력들을 실행. 크래시 시 fix 디버깅 루프."""
    inputs = [inp for _, inp in cand]
    results = []
    for attempt in range(max_fix + 1):
        results = _eval_batch(solution, inputs, timeout, poll)
        crash = next(
            ((i, r) for i, r in enumerate(results)
             if not r["timed_out"] and r["returncode"] not in (0, None)),
            None,
        )
        if crash is None or attempt == max_fix:
            return solution, results
        i, r = crash
        data = _call(
            user, "testcase_fix", "/ai/authoring/fix",
            {
                **base_payload,
                "solution_code": solution,
                "error": (r["stderr"] or "")[:1500],
                "sample_input": cand[i][1][:1000],
            },
        )
        solution = data["solution_code"]
    return solution, results


def generate_testcases(problem, *, user=None, seeds=30, timeout=5, poll=180, max_fix=1, log=None):
    """TC 리스트 생성(저장 안 함). 반환: {test_cases, counts}."""
    emit = log or (lambda *a: None)
    base_payload = {
        "problem_id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "constraints": problem.constraints,
    }

    gen = _call(user, "testcase_gen", "/ai/authoring/generate", base_payload)
    solution = gen["solution_code"]
    generator = gen["generator_code"]
    edge_inputs = gen.get("edge_inputs", [])
    time_inputs = gen.get("time_inputs", [])
    emit(f"생성: solution {len(solution)}B · generator {len(generator)}B · edge {len(edge_inputs)} · time {len(time_inputs)}")

    seed_list = [str(i) for i in range(seeds)]
    gen_results = _eval_batch(generator, seed_list, timeout, poll)
    random_inputs = [
        r["stdout"]
        for r in gen_results
        if r["returncode"] == 0 and not r["timed_out"] and r["stdout"].strip()
    ]
    emit(f"랜덤 입력 {len(random_inputs)}/{len(seed_list)}개")

    cand = (
        [("edge", s) for s in edge_inputs]
        + [("time", s) for s in time_inputs]
        + [("random", s) for s in random_inputs]
    )
    solution, sol_results = _run_solution(user, base_payload, solution, cand, timeout, poll, max_fix)

    test_cases = []
    for (kind, inp), r in zip(cand, sol_results):
        if r["returncode"] == 0 and not r["timed_out"]:
            test_cases.append({
                "kind": kind,
                "input": inp,
                "expected_output": r["stdout"],
                "elapsed_ms": r["elapsed_ms"],
                "compare_mode": "line_trim",
            })
    counts = {k: sum(1 for t in test_cases if t["kind"] == k) for k in ("random", "edge", "time")}
    counts["total"] = len(test_cases)
    emit(f"최종 TC {counts}")
    return {"test_cases": test_cases, "counts": counts}


def generate_and_save(problem, *, user=None, seeds=20, **kwargs):
    """TC 생성 후 problems.TestCase 로 저장. 이미 있으면 skip. 반환 요약."""
    from problems.models import TestCase

    if problem.test_cases.exists():
        return {"created": 0, "skipped": "already_has_testcases"}

    result = generate_testcases(problem, user=user, seeds=seeds, **kwargs)
    tcs = result["test_cases"]
    if not tcs:
        return {"created": 0, "skipped": "no_testcases_generated"}

    edge_seen = 0
    objs = []
    for t in tcs:
        is_sample = False
        if t["kind"] == "edge" and edge_seen < 2:  # 엣지 앞 2개를 예제(공개)로
            is_sample = True
            edge_seen += 1
        objs.append(TestCase(
            problem=problem,
            input_data=t["input"],
            expected_output=t["expected_output"],
            compare_mode=t.get("compare_mode", "line_trim"),
            is_sample=is_sample,
        ))
    TestCase.objects.bulk_create(objs)
    return {"created": len(objs), "counts": result["counts"]}
