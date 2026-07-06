"""Code execution submission endpoints."""
import json

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from gamification.services import record_user_action
from problems.models import Problem

from .models import ExecutionJob, Submission


FINISHED_JOB_STATUSES = {"success", "failed", "timeout"}
ACTIVE_JOB_STATUSES = {"pending", "running"}


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
        return JsonResponse({"ok": False, "error_message": "코드를 작성해주세요."}, status=400)

    problem = get_object_or_404(Problem, pk=problem_id, is_active=True)

    with transaction.atomic():
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            code=code,
            result="pending",
            submission_type=submission_type,
        )
        job = ExecutionJob.objects.create(
            user=request.user,
            submission=submission,
            job_type=job_type,
            status="pending",
            input_payload={
                "problem_id": problem.id,
                "submission_id": submission.id,
                "submission_type": submission_type,
            },
        )
    if submission_type == "submit":
        record_user_action(request.user, "submission_created", submission)

    return JsonResponse(
        {
            "ok": True,
            "submission_id": submission.id,
            "job_id": job.id,
            "job_status": job.status,
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
