import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from problems.models import Problem, ProblemCategory
from submissions.models import Submission

from .models import WrongNote


class WrongNoteCreateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="note-user",
            password="pass12345",
        )
        self.category = ProblemCategory.objects.create(
            name="알고리즘",
            slug="algorithms",
        )
        self.problem = Problem.objects.create(
            category=self.category,
            title="세 수의 합",
            description="세 수의 합이 0인지 찾으세요.",
            difficulty="intermediate",
        )
        self.submission = Submission.objects.create(
            user=self.user,
            problem=self.problem,
            code="print(0)",
            result="wrong",
            submission_type="submit",
        )
        self.client.force_login(self.user)

    @patch("wrongnotes.views.analyze_wrong_note")
    def test_create_wrong_note_for_wrong_submission(self, mock_analyze):
        mock_analyze.return_value = {
            "similar_notes": [],
            "analysis": {"cause": "stub cause"},
            "errors": [],
        }

        response = self.client.post(
            reverse("wrongnotes:create", args=[self.submission.id]),
            data=json.dumps({"comment": "포인터 이동 조건을 잘못 잡았다."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        note = WrongNote.objects.get(pk=body["wrong_note_id"])
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.submission, self.submission)
        self.assertEqual(note.status, "completed")
        self.assertEqual(note.ai_analysis["analysis"]["cause"], "stub cause")

    def test_success_submission_cannot_create_wrong_note(self):
        self.submission.result = "success"
        self.submission.save(update_fields=["result"])

        response = self.client.post(
            reverse("wrongnotes:create", args=[self.submission.id]),
            data=json.dumps({"comment": "성공 제출"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(WrongNote.objects.exists())
