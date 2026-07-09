import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from logs.models import LLMRequestLog
from problems.models import Problem, ProblemCategory
from submissions.models import Submission
from wrongnotes.models import WrongNote

from .models import CodingState
from .services import batch_refresh, gather_stats, refresh, select_stale_user_ids


class BatchRefreshSelectionTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.category = ProblemCategory.objects.create(name="알고리즘", slug="algo")
        self.problem = Problem.objects.create(
            category=self.category, title="문제", description="d", difficulty="beginner"
        )

    def _user(self, name):
        return self.User.objects.create_user(username=name, password="pass12345")

    def _submit(self, user, n=1):
        for _ in range(n):
            Submission.objects.create(
                user=user, problem=self.problem, code="x",
                result="success", submission_type="submit",
            )

    def _state(self, user, source_count):
        return CodingState.objects.create(
            user=user, summary="s", level="초급", source_submission_count=source_count
        )

    def test_select_stale_picks_new_and_accumulated_only(self):
        fresh = self._user("fresh")       # 상태의 기준치와 제출수 동일 → 제외
        self._submit(fresh, 5)
        self._state(fresh, source_count=5)

        stale_new = self._user("new")     # 상태 없음 → 대상
        self._submit(stale_new, 2)

        stale_acc = self._user("acc")     # 신규 6건 누적(>=5) → 대상
        self._submit(stale_acc, 8)
        self._state(stale_acc, source_count=2)

        no_submit = self._user("idle")    # 제출 없음 → 후보 아님

        ids = select_stale_user_ids(min_new_submissions=5)

        self.assertIn(stale_new.id, ids)
        self.assertIn(stale_acc.id, ids)
        self.assertNotIn(fresh.id, ids)
        self.assertNotIn(no_submit.id, ids)

    def test_force_selects_all_with_submits(self):
        fresh = self._user("fresh")
        self._submit(fresh, 3)
        self._state(fresh, source_count=3)
        ids = select_stale_user_ids(force=True)
        self.assertIn(fresh.id, ids)

    @patch("codingstate.services.refresh")
    def test_batch_refresh_only_refreshes_stale_and_respects_limit(self, mock_refresh):
        mock_refresh.return_value = Mock(level="중급")  # non-None = 성공
        u1 = self._user("u1"); self._submit(u1, 3)
        u2 = self._user("u2"); self._submit(u2, 3)
        u3 = self._user("u3"); self._submit(u3, 3)

        summary = batch_refresh(min_new_submissions=5, limit=2)

        self.assertEqual(summary["candidates"], 3)
        self.assertEqual(summary["stale"], 3)      # 셋 다 상태 없음 → stale
        self.assertEqual(summary["processed"], 2)  # limit 적용
        self.assertEqual(summary["refreshed"], 2)
        self.assertEqual(mock_refresh.call_count, 2)

    @patch("codingstate.services.refresh")
    def test_batch_refresh_counts_failures(self, mock_refresh):
        mock_refresh.return_value = None  # 갱신 실패(FastAPI 오류 등)
        u = self._user("u"); self._submit(u, 2)
        summary = batch_refresh(min_new_submissions=5)
        self.assertEqual(summary["refreshed"], 0)
        self.assertEqual(summary["failed"], 1)


class ThinkingMemoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="thinker", password="pass12345"
        )
        self.category = ProblemCategory.objects.create(name="알고리즘", slug="algo")
        self.problem = Problem.objects.create(
            category=self.category, title="이분탐색", description="d", difficulty="beginner"
        )

    def _submission(self, code, result="wrong"):
        return Submission.objects.create(
            user=self.user, problem=self.problem, code=code,
            result=result, submission_type="submit",
        )

    def test_gather_stats_includes_thinking_inputs(self):
        self._submission("while lo < hi:  # off-by-one 의심", result="wrong")
        submission = self._submission("print(0)", result="wrong")
        WrongNote.objects.create(
            user=self.user, problem=self.problem, submission=submission,
            comment="경계 조건을 자꾸 놓친다", error_pattern="off-by-one",
            status="completed",
            ai_analysis={"analysis": {"cause": "mid 계산과 종료조건 혼동"}},
        )
        LLMRequestLog.objects.create(
            user=self.user, request_type="tutor_chat", request_id="q-1",
            input_text=json.dumps({"question": "이분탐색이 왜 무한루프에 빠지죠?"}),
            status="success",
        )

        stats = gather_stats(self.user)

        self.assertIn("recent_code", stats)
        self.assertTrue(any("off-by-one" in c["code"] for c in stats["recent_code"]))
        self.assertEqual(stats["retrospections"][0]["comment"], "경계 조건을 자꾸 놓친다")
        self.assertEqual(stats["retrospections"][0]["cause"], "mid 계산과 종료조건 혼동")
        self.assertIn("이분탐색이 왜 무한루프에 빠지죠?", stats["recent_questions"])

    @patch("codingstate.services.call_fastapi")
    def test_refresh_feeds_previous_memory_and_saves_thinking(self, mock_call):
        self._submission("print(1)", result="success")
        CodingState.objects.create(
            user=self.user, summary="예전 요약", thinking_profile="예전 사고",
            source_submission_count=0, refresh_count=2,
        )
        mock_call.return_value = Mock(data={
            "summary": "갱신 요약",
            "thinking_profile": "가설을 급하게 세우고 경계값 확인을 건너뛴다",
            "level": "초급",
            "strengths": [], "weaknesses": ["이분탐색"],
            "recurring_mistakes": [], "recommended_focus": [],
            "model": "gpt-4o-mini",
        })

        state = refresh(self.user)

        # 직전 메모리가 입력으로 전달됨(rolling)
        payload_stats = mock_call.call_args.kwargs["payload"]["stats"]
        self.assertEqual(payload_stats["previous_summary"], "예전 요약")
        self.assertEqual(payload_stats["previous_thinking"], "예전 사고")
        # 사고 메모리 저장 + 갱신 횟수 증가
        self.assertEqual(state.thinking_profile, "가설을 급하게 세우고 경계값 확인을 건너뛴다")
        self.assertEqual(state.refresh_count, 3)

    def test_prompt_context_includes_thinking(self):
        CodingState.objects.create(
            user=self.user, summary="요약", thinking_profile="경계값을 자주 놓침",
            level="초급",
        )
        from .services import get_prompt_context
        ctx = get_prompt_context(self.user)
        self.assertIn("사고 특성: 경계값을 자주 놓침", ctx)
