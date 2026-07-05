from django.contrib.auth import get_user_model
from django.test import TestCase

from problems.models import Problem, ProblemCategory
from submissions.models import Submission

from .models import Mission, PointLog, UserMission
from .services import award_points, record_user_action


class GamificationServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="point-user",
            password="pass12345",
        )
        category = ProblemCategory.objects.create(name="알고리즘", slug="algorithms")
        problem = Problem.objects.create(
            category=category,
            title="합 구하기",
            description="두 수의 합을 구하세요.",
            difficulty="beginner",
        )
        self.submission = Submission.objects.create(
            user=self.user,
            problem=problem,
            code="print(3)",
            result="success",
            submission_type="submit",
        )

    def test_award_points_is_idempotent_by_related_object(self):
        first_log, first_created = award_points(
            self.user,
            "submission_created",
            self.submission,
        )
        second_log, second_created = award_points(
            self.user,
            "submission_created",
            self.submission,
        )

        self.user.refresh_from_db()
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_log.id, second_log.id)
        self.assertEqual(self.user.point, 10)
        self.assertEqual(PointLog.objects.count(), 1)

    def test_record_user_action_advances_matching_mission_only(self):
        matching = Mission.objects.create(
            title="오늘 문제 1개 풀기",
            trigger_action="submission_created",
            target_count=1,
            reward_point=30,
        )
        Mission.objects.create(
            title="오답노트 1개 작성하기",
            trigger_action="wrongnote_completed",
            target_count=1,
            reward_point=30,
        )

        result = record_user_action(
            self.user,
            "submission_created",
            self.submission,
        )

        self.user.refresh_from_db()
        user_mission = UserMission.objects.get(user=self.user, mission=matching)
        self.assertTrue(result["point_created"])
        self.assertTrue(user_mission.is_completed)
        self.assertEqual(user_mission.progress_count, 1)
        self.assertEqual(self.user.point, 40)
        self.assertEqual(PointLog.objects.count(), 2)
        self.assertEqual(UserMission.objects.count(), 1)
