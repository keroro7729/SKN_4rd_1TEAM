"""마이페이지·계정관리 테스트 (FR-ACC-001/003, FR-MYPAGE-001).

- 계정 민감 화면 재인증 게이트
- 아바타 해금 포인트 조건
- 마이페이지 학습 현황 렌더
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

STRONG_PW = "Testpass!234"


class AccountVerificationGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password=STRONG_PW)
        self.client.force_login(self.user)

    def test_account_detail_requires_reverification(self):
        """비밀번호 재확인 세션 없이 계정 상세 접근 → 재인증 화면으로 리다이렉트."""
        resp = self.client.get(reverse("mypage:account_detail"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("mypage:account_verify"), resp.url)

    def test_password_change_requires_reverification(self):
        resp = self.client.get(reverse("mypage:password_change"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("mypage:account_verify"), resp.url)


class AvatarUnlockTests(TestCase):
    def test_locked_avatar_not_selectable(self):
        user = User.objects.create_user(username="poor", password=STRONG_PW, point=0)
        self.client.force_login(user)
        self.client.post(reverse("mypage:avatar"), {"avatar_key": "dragon"})  # 800P 필요
        user.refresh_from_db()
        self.assertEqual(user.selected_avatar, "cat")  # 변경되지 않음

    def test_unlocked_avatar_selectable(self):
        user = User.objects.create_user(username="rich", password=STRONG_PW, point=800)
        self.client.force_login(user)
        self.client.post(reverse("mypage:avatar"), {"avatar_key": "dragon"})
        user.refresh_from_db()
        self.assertEqual(user.selected_avatar, "dragon")


class MyPageRenderTests(TestCase):
    def test_mypage_renders_for_logged_in_user(self):
        user = User.objects.create_user(username="learner", password=STRONG_PW)
        self.client.force_login(user)
        resp = self.client.get(reverse("mypage:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("summary", resp.context)
