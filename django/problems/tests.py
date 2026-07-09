from django.contrib.auth import get_user_model
from django.test import TestCase

from submissions.models import Submission

from .models import Problem, ProblemCategory, ProblemTag
from .services.recommend import recommend_problems


class RecommendProblemsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="learner", password="pass12345"
        )
        self.category = ProblemCategory.objects.create(name="알고리즘", slug="algo")
        self.dp = ProblemTag.objects.create(name="DP", slug="dp")
        self.graph = ProblemTag.objects.create(name="그래프", slug="graph")

    def _problem(self, title, difficulty="beginner", tags=(), active=True):
        problem = Problem.objects.create(
            category=self.category,
            title=title,
            description="설명",
            difficulty=difficulty,
            is_active=active,
        )
        if tags:
            problem.tags.set(tags)
        return problem

    def _submit(self, problem, result):
        return Submission.objects.create(
            user=self.user,
            problem=problem,
            code="print(1)",
            result=result,
            submission_type="submit",
        )

    def test_weak_tag_problem_recommended_first(self):
        failed_dp = self._problem("틀린 DP 문제", tags=[self.dp])
        self._submit(failed_dp, "wrong")  # DP 취약 신호 생성
        fresh_dp = self._problem("새 DP 문제", tags=[self.dp])  # 취약 유형 보강 대상
        fresh_graph = self._problem("새 그래프 문제", tags=[self.graph])
        current = self._problem("지금 푸는 문제", tags=[self.dp])

        recs = recommend_problems(self.user, current=current, limit=3)
        rec_ids = [r["problem"].id for r in recs]

        # 현재 문제와 이미 제출한 문제는 후보에서 제외
        self.assertNotIn(current.id, rec_ids)
        self.assertNotIn(failed_dp.id, rec_ids)
        # 취약 태그(DP) 문제가 1순위 + 사유 라벨
        self.assertEqual(recs[0]["problem"].id, fresh_dp.id)
        self.assertEqual(recs[0]["reason"], "취약 유형 보강")
        # 나머지는 '새 도전'으로 채워짐
        self.assertIn(fresh_graph.id, rec_ids)

    def test_excludes_solved_and_inactive(self):
        solved = self._problem("이미 푼 문제", tags=[self.dp])
        self._submit(solved, "success")
        inactive = self._problem("비활성 문제", tags=[self.dp], active=False)
        available = self._problem("풀 수 있는 문제", tags=[self.graph])

        rec_ids = [r["problem"].id for r in recommend_problems(self.user, limit=5)]

        self.assertNotIn(solved.id, rec_ids)
        self.assertNotIn(inactive.id, rec_ids)
        self.assertIn(available.id, rec_ids)

    def test_no_candidates_returns_empty(self):
        only = self._problem("유일한 문제")
        recs = recommend_problems(self.user, current=only, limit=3)
        self.assertEqual(recs, [])
