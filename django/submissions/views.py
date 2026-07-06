"""코드 실행/결과 뷰 (STEP-04).

- CodeRunView(POST /submissions/run/): Submission + ExecutionJob(pending) 생성. 실제 실행은 Worker.
- SubmissionResultView(GET /submissions/<id>/result/): job_status + submission_result 등 폴링 결과 반환.

JSON I/O (STEP-07 Fetch 연동 대상). 권한: 로그인 필요 + 본인 제출만 조회.
포인트 지급(submission_created/solve_success)은 STEP-08.
"""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from problems.models import Problem

from .models import ExecutionJob, Submission

_TERMINAL = ("success", "failed", "timeout")


class CodeRunView(LoginRequiredMixin, View):
    """코드 제출 → 제출/실행Job 생성 후 식별자 반환 (실행은 Worker가 polling)."""

    def post(self, request):
        try:
            data = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            data = request.POST

        problem_id = data.get("problem_id")
        code = (data.get("code") or "")
        mode = data.get("mode") or "submit"  # run: 1번 테스트케이스 / submit: 전체
        if mode not in ("run", "submit"):
            mode = "submit"
        if not problem_id or not str(code).strip():
            return JsonResponse({"error": "problem_id 와 code 가 필요합니다."}, status=400)

        problem = get_object_or_404(Problem, pk=problem_id)
        submission = Submission.objects.create(
            user=request.user, problem=problem, code=code, result="pending"
        )
        job = ExecutionJob.objects.create(
            user=request.user,
            submission=submission,
            job_type="code_run",
            status="pending",
            input_payload={"problem_id": problem.id, "mode": mode},
        )
        return JsonResponse(
            {"submission_id": submission.id, "job_id": job.id, "status": "pending"},
            status=201,
        )


class SubmissionResultView(LoginRequiredMixin, View):
    """폴링용 결과 조회. 본인 제출만 허용."""

    def get(self, request, pk):
        submission = get_object_or_404(
            Submission.objects.select_related("problem"), pk=pk, user=request.user
        )
        job = submission.jobs.order_by("-id").first()
        job_status = job.status if job else "pending"
        return JsonResponse(
            {
                "submission_id": submission.id,
                "job_status": job_status,
                "submission_result": submission.result,
                "is_finished": job_status in _TERMINAL,
                "output": submission.output,
                "error_message": submission.error_message,
                "elapsed_ms": submission.elapsed_ms,
                "detail": (job.result_payload if job else {}),  # {mode,result,passed,total,input,expected,actual}
            }
        )
