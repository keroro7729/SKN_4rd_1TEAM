import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from problems.models import Problem, ProblemCategory

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
