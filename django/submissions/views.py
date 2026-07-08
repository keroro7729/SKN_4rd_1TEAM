"""Code execution submission endpoints."""
import json
import logging
import threading
import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import connections, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from gamification.services import record_user_action
from problems.models import Problem

from .models import ExecutionJob, Submission

logger = logging.getLogger(__name__)

FINISHED_JOB_STATUSES = {"success", "failed", "timeout"}
ACTIVE_JOB_STATUSES = {"pending", "running"}

# 문제당 최초 1회 TC 자동생성이 걸릴 수 있는 최대 시간(초).
# 이 시간이 지난 생성 마커/대기는 죽은 것으로 간주(스레드·워커 프로세스 사망 대비).
TESTCASE_GEN_TIMEOUT_SEC = 300


def _expire_stale_job(job):
    """Finish stale jobs so the browser never waits indefinitely."""
    if job is None or job.status not in ACTIVE_JOB_STATUSES:
        return

    base_time = job.started_at or job.created_at
    elapsed_sec = (timezone.now() - base_time).total_seconds()
    if elapsed_sec < settings.CODE_JOB_RESULT_TIMEOUT_SEC:
        return

    message = (
        "코드 실행 Worker 응답이 지연되었습니다. "
        "Worker 서버 상태와 로그를 확인해 주세요."
    )
    payload = {
        "passed": 0,
        "total": 0,
        "case_results": [],
        "stdout": "",
        "stderr": "",
        "error_message": message,
        "elapsed_ms": int(elapsed_sec * 1000),
    }
    submission = job.submission
    submission.result = "error"
    submission.output = ""
    submission.error_message = message
    submission.elapsed_ms = payload["elapsed_ms"]
    submission.save(update_fields=["result", "output", "error_message", "elapsed_ms"])

    job.status = "failed"
    job.result_payload = payload
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "result_payload", "finished_at"])


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


def _active_gen_marker(problem_id):
    """진행 중(신선한) testcase_gen 마커 반환. 없거나 오래됐으면(죽은 것으로 간주) None."""
    fresh_after = timezone.now() - timedelta(seconds=TESTCASE_GEN_TIMEOUT_SEC)
    return (
        ExecutionJob.objects.filter(
            job_type="testcase_gen",
            status__in=ACTIVE_JOB_STATUSES,
            created_at__gte=fresh_after,
            input_payload__problem_id=problem_id,
        )
        .order_by("-id")
        .first()
    )


def _enqueue_code_job(submission, submission_type: str, job_type: str):
    """Worker 가 처리할 실제 코드 실행/제출 잡을 등록."""
    return ExecutionJob.objects.create(
        user=submission.user,
        submission=submission,
        job_type=job_type,
        status="pending",
        input_payload={
            "problem_id": submission.problem_id,
            "submission_id": submission.id,
            "submission_type": submission_type,
        },
    )


def _generate_then_enqueue(*, submission_id, problem_id, submission_type, job_type, user_id, marker_id):
    """백그라운드 스레드: (담당이면) TC 생성 → 완료 후 실행 잡 등록.

    gunicorn 요청 스레드를 블록하지 않기 위한 처리(문제당 최초 1회). MVP 라 태스크 큐
    없이 daemon thread 사용. 실행 잡은 TC 준비가 끝난 뒤에만 등록되므로 Worker 가
    '무(無) TC' 로 즉시 실패하는 일이 없다. 생성 실패 시에도 실행 잡은 등록하여
    Worker 가 '테스트케이스 없음' 을 정상 결과로 돌려준다(무한 대기 방지).
    """
    from problems.models import Problem
    from problems.services.testcase_agent import TestcaseAgentError, generate_and_save

    try:
        problem = Problem.objects.filter(pk=problem_id).first()
        if problem is None:
            return

        if marker_id is not None:
            # 생성 담당(winner): 실제로 생성하고 마커 상태를 종료 처리
            gen_status = "success"
            try:
                if not problem.test_cases.exists():
                    user = get_user_model().objects.filter(pk=user_id).first()
                    generate_and_save(problem, user=user)
            except TestcaseAgentError:
                gen_status = "failed"
            except Exception:  # noqa: BLE001 - 생성 실패해도 실행 잡은 등록해야 함
                gen_status = "failed"
                logger.exception("testcase generation crashed (problem=%s)", problem_id)
            ExecutionJob.objects.filter(pk=marker_id).update(
                status=gen_status, finished_at=timezone.now()
            )
        else:
            # 생성 대기(loser): 담당 스레드가 TC 를 넣을 때까지 폴링
            deadline = time.monotonic() + TESTCASE_GEN_TIMEOUT_SEC
            while time.monotonic() < deadline and not problem.test_cases.exists():
                time.sleep(1)
    finally:
        try:
            submission = Submission.objects.filter(pk=submission_id).first()
            if submission is not None and not submission.jobs.exists():
                _enqueue_code_job(submission, submission_type, job_type)
        except Exception:  # noqa: BLE001
            logger.exception("failed to enqueue code job after generation (sub=%s)", submission_id)
        finally:
            connections.close_all()  # 스레드 로컬 DB 커넥션 반납


def _create_code_job(request, *, submission_type: str, job_type: str):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"ok": False, "error_message": "invalid_json"}, status=400)

    problem_id = payload.get("problem_id")
    code = payload.get("code") or ""
    if not problem_id:
        return JsonResponse(
            {"ok": False, "error_message": "problem_id_required"},
            status=400,
        )
    if not code.strip():
        return JsonResponse({"ok": False, "error_message": "code_required"}, status=400)

    problem = get_object_or_404(Problem, pk=problem_id, is_active=True)

    # TC 가 있으면 즉시 실행 잡 등록. 없으면 백그라운드에서 생성 후 등록(요청은 블록하지 않음).
    # 동일 문제 동시 요청은 problem 행을 select_for_update 로 직렬화해 중복 생성을 막는다.
    marker_id = None
    with transaction.atomic():
        locked_problem = Problem.objects.select_for_update().get(pk=problem.pk)
        has_tcs = locked_problem.test_cases.exists()
        submission = Submission.objects.create(
            user=request.user,
            problem=locked_problem,
            code=code,
            result="pending",
            submission_type=submission_type,
        )
        job = None
        if has_tcs:
            job = _enqueue_code_job(submission, submission_type, job_type)
        elif _active_gen_marker(locked_problem.pk) is None:
            # 이 요청이 생성 담당. 마커를 남겨 다른 동시 요청은 대기 역할로 만든다.
            marker = ExecutionJob.objects.create(
                job_type="testcase_gen",
                status="running",
                started_at=timezone.now(),
                input_payload={"problem_id": locked_problem.pk},
            )
            marker_id = marker.pk

    if submission_type == "submit":
        record_user_action(request.user, "submission_created", submission)

    if job is None:
        threading.Thread(
            target=_generate_then_enqueue,
            kwargs={
                "submission_id": submission.id,
                "problem_id": problem.id,
                "submission_type": submission_type,
                "job_type": job_type,
                "user_id": request.user.id,
                "marker_id": marker_id,
            },
            daemon=True,
        ).start()
        job_id = None
        job_status = "generating"
    else:
        job_id = job.id
        job_status = job.status

    return JsonResponse(
        {
            "ok": True,
            "submission_id": submission.id,
            "job_id": job_id,
            "job_status": job_status,
            "submission_result": submission.result,
            "submission_type": submission.submission_type,
        },
        status=202,
    )


@login_required
@require_POST
def run_submission(request):
    """Create a practice run job. Runs are hidden from final submission history."""
    return _create_code_job(request, submission_type="run", job_type="code_run")


@login_required
@require_POST
def submit_submission(request):
    """Create a final submission job that remains in user submission history."""
    return _create_code_job(request, submission_type="submit", job_type="code_submit")


@login_required
@require_GET
def submission_result(request, submission_id):
    """Return the current execution result for polling."""
    submission = get_object_or_404(
        Submission.objects.filter(user=request.user).select_related("problem"),
        pk=submission_id,
    )
    job = submission.jobs.order_by("-created_at", "-id").first()
    _expire_stale_job(job)
    if job is not None:
        submission.refresh_from_db(fields=["result", "output", "error_message", "elapsed_ms"])
        job.refresh_from_db(fields=["status", "result_payload"])
    payload = job.result_payload if job else {}
    job_status = job.status if job else "pending"
    # 실행 잡이 아직 없고 TC 자동생성이 진행 중이면 'generating' 으로 알려 클라이언트가
    # 더 오래 기다리도록 한다(최초 1회 생성은 수십 초 걸릴 수 있음).
    if job is None and _active_gen_marker(submission.problem_id) is not None:
        job_status = "generating"
    output = submission.output or payload.get("stdout", "") or payload.get("output", "")
    error_message = submission.error_message or payload.get("error_message", "")
    elapsed_ms = submission.elapsed_ms
    if elapsed_ms is None:
        elapsed_ms = payload.get("elapsed_ms", 0)
    wrong_note_create_url = None
    if (
        submission.submission_type == "submit"
        and submission.result in {"wrong", "error", "timeout"}
    ):
        wrong_note_create_url = reverse("wrongnotes:create", args=[submission.id])
    if (
        submission.submission_type == "submit"
        and submission.result == "success"
        and job_status in FINISHED_JOB_STATUSES
    ):
        record_user_action(request.user, "solve_success", submission)

    return JsonResponse(
        {
            "submission_id": submission.id,
            "problem_id": submission.problem_id,
            "submission_type": submission.submission_type,
            "job_status": job_status,
            "submission_result": submission.result,
            "is_finished": job_status in FINISHED_JOB_STATUSES,
            "output": output,
            "error_message": error_message,
            "elapsed_ms": elapsed_ms,
            "total": payload.get("total", 0),
            "passed": payload.get("passed", 0),
            "case_results": payload.get("case_results", []),
            "wrong_note_create_url": wrong_note_create_url,
            "job": {
                "id": job.id if job else None,
                "status": job_status,
                "result_payload": payload,
            },
        }
    )
