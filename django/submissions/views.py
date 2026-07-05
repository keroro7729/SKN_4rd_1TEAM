"""Code execution submission endpoints."""
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from problems.models import Problem

from .models import ExecutionJob, Submission


@login_required
@require_POST
def run_submission(request):
    """Create a Submission and enqueue a code_run ExecutionJob."""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    problem_id = payload.get("problem_id")
    code = (payload.get("code") or "").strip()
    if not problem_id:
        return JsonResponse({"error": "problem_id_required"}, status=400)
    if not code:
        return JsonResponse({"error": "code_required"}, status=400)

    problem = get_object_or_404(Problem, pk=problem_id, is_active=True)

    with transaction.atomic():
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            code=code,
            result="pending",
        )
        job = ExecutionJob.objects.create(
            user=request.user,
            submission=submission,
            job_type="code_run",
            status="pending",
            input_payload={"problem_id": problem.id},
        )

    return JsonResponse(
        {
            "submission_id": submission.id,
            "job_id": job.id,
            "status": job.status,
            "result": submission.result,
        },
        status=202,
    )


@login_required
@require_GET
def submission_result(request, submission_id):
    """Return the current execution result for polling."""
    submission = get_object_or_404(
        Submission.objects.filter(user=request.user).select_related("problem"),
        pk=submission_id,
    )
    job = submission.jobs.order_by("-created_at", "-id").first()
    return JsonResponse(
        {
            "submission_id": submission.id,
            "problem_id": submission.problem_id,
            "result": submission.result,
            "output": submission.output,
            "error_message": submission.error_message,
            "elapsed_ms": submission.elapsed_ms,
            "job": {
                "id": job.id if job else None,
                "status": job.status if job else None,
                "result_payload": job.result_payload if job else {},
            },
        }
    )
