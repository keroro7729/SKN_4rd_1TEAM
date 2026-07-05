"""Code execution submission endpoints."""
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from problems.models import Problem

from .models import ExecutionJob, Submission


FINISHED_JOB_STATUSES = {"success", "failed", "timeout"}


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
        return JsonResponse({"ok": False, "error_message": "code_required"}, status=400)

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
    payload = job.result_payload if job else {}
    job_status = job.status if job else "pending"
    output = submission.output or payload.get("stdout", "") or payload.get("output", "")
    error_message = submission.error_message or payload.get("error_message", "")
    elapsed_ms = submission.elapsed_ms
    if elapsed_ms is None:
        elapsed_ms = payload.get("elapsed_ms", 0)

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
            "job": {
                "id": job.id if job else None,
                "status": job_status,
                "result_payload": payload,
            },
        }
    )
