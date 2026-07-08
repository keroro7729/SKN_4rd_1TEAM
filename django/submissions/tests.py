import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from problems.models import Problem, ProblemCategory
from problems.models import TestCase as ProblemTestCase
from gamification.models import PointLog

from .models import ExecutionJob, Submission


class SubmissionEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="runner",
            password="pass12345",
        )
        self.category = ProblemCategory.objects.create(
            name="알고리즘",
            slug="algorithms",
        )
        self.problem = Problem.objects.create(
            category=self.category,
            title="두 수의 합",
            description="두 수를 더해 출력하세요.",
            difficulty="beginner",
        )
        # TC 가 있는 문제는 즉시 실행 잡을 등록한다(동기 경로).
        ProblemTestCase.objects.create(
            problem=self.problem,
            input_data="1 2",
            expected_output="3",
        )
        self.client.force_login(self.user)

    def post_code(self, url_name):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(
                {
                    "problem_id": self.problem.id,
                    "code": "print(sum(map(int, input().split())))",
                }
            ),
            content_type="application/json",
        )

    def test_run_creates_practice_submission_and_code_run_job(self):
        response = self.post_code("submissions:run")

        self.assertEqual(response.status_code, 202)
        body = response.json()
        submission = Submission.objects.get(pk=body["submission_id"])
        job = ExecutionJob.objects.get(pk=body["job_id"])

        self.assertEqual(submission.submission_type, "run")
        self.assertEqual(job.job_type, "code_run")
        self.assertEqual(body["job_status"], "pending")
        self.assertEqual(body["submission_result"], "pending")

    def test_submit_creates_final_submission_and_code_submit_job(self):
        response = self.post_code("submissions:submit")

        self.assertEqual(response.status_code, 202)
        body = response.json()
        submission = Submission.objects.get(pk=body["submission_id"])
        job = ExecutionJob.objects.get(pk=body["job_id"])

        self.assertEqual(submission.submission_type, "submit")
        self.assertEqual(job.job_type, "code_submit")
        self.user.refresh_from_db()
        self.assertEqual(self.user.point, 10)
        self.assertTrue(
            PointLog.objects.filter(
                user=self.user,
                action_type="submission_created",
                related_model="submission",
                related_id=submission.id,
            ).exists()
        )

    def test_run_without_testcases_defers_generation_and_does_not_block(self):
        """TC 없는 문제는 요청을 블록하지 않고 백그라운드 생성으로 넘긴다(근본 수정)."""
        problem_no_tc = Problem.objects.create(
            category=self.category,
            title="TC 없는 문제",
            description="아직 테스트케이스가 없습니다.",
            difficulty="beginner",
        )
        with patch("submissions.views.threading.Thread") as thread_cls:
            response = self.client.post(
                reverse("submissions:run"),
                data=json.dumps({"problem_id": problem_no_tc.id, "code": "print(1)"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        # 실행 잡은 아직 없고(생성 후 등록), 클라이언트에 'generating' 을 알린다.
        self.assertIsNone(body["job_id"])
        self.assertEqual(body["job_status"], "generating")
        self.assertFalse(
            ExecutionJob.objects.filter(job_type="code_run").exists()
        )
        # 생성 담당 마커가 남고, 백그라운드 생성 스레드가 그 마커로 스케줄된다.
        marker = ExecutionJob.objects.get(
            job_type="testcase_gen", status="running"
        )
        self.assertEqual(marker.input_payload["problem_id"], problem_no_tc.id)
        thread_cls.return_value.start.assert_called_once()
        # 백그라운드 함수에 전달되는 인자(kwargs=)에 담당 마커 id 가 실려야 한다.
        worker_kwargs = thread_cls.call_args.kwargs["kwargs"]
        self.assertEqual(worker_kwargs["marker_id"], marker.id)
        self.assertEqual(worker_kwargs["submission_id"], body["submission_id"])

    def test_result_reports_generating_while_marker_active(self):
        """실행 잡이 아직 없고 생성 마커가 살아있으면 result 는 generating 을 준다."""
        problem_no_tc = Problem.objects.create(
            category=self.category,
            title="생성중 문제",
            description="생성 중",
            difficulty="beginner",
        )
        submission = Submission.objects.create(
            user=self.user,
            problem=problem_no_tc,
            code="print(1)",
            result="pending",
            submission_type="run",
        )
        ExecutionJob.objects.create(
            job_type="testcase_gen",
            status="running",
            started_at=timezone.now(),
            input_payload={"problem_id": problem_no_tc.id},
        )

        response = self.client.get(
            reverse("submissions:result", args=[submission.id])
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["job_status"], "generating")
        self.assertFalse(body["is_finished"])

    def test_result_response_exposes_step04_polling_fields(self):
        submission = Submission.objects.create(
            user=self.user,
            problem=self.problem,
            code="print(3)",
            result="success",
            submission_type="submit",
            output="3\n",
            elapsed_ms=12,
        )
        ExecutionJob.objects.create(
            user=self.user,
            submission=submission,
            job_type="code_submit",
            status="success",
            result_payload={"passed": 2, "total": 2, "case_results": []},
        )

        response = self.client.get(
            reverse("submissions:result", args=[submission.id])
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["job_status"], "success")
        self.assertEqual(body["submission_result"], "success")
        self.assertTrue(body["is_finished"])
        self.assertEqual(body["output"], "3\n")
        self.assertEqual(body["elapsed_ms"], 12)
        self.assertEqual(body["passed"], 2)
        self.assertEqual(body["total"], 2)
        self.user.refresh_from_db()
        self.assertEqual(self.user.point, 20)
        self.assertTrue(
            PointLog.objects.filter(
                user=self.user,
                action_type="solve_success",
                related_model="submission",
                related_id=submission.id,
            ).exists()
        )
