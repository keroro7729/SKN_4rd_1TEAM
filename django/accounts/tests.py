"""회원·인증·권한 테스트 (FR-AUTH-001/002/003).

- 회원가입 폼 검증 및 계정 생성/자동 로그인
- 로그인·로그아웃 세션 처리
- 비로그인 보호 URL 리다이렉트, 일반 사용자의 관리자 화면 접근 차단
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

STRONG_PW = "Testpass!234"


class SignupTests(TestCase):
    def test_signup_creates_user_and_auto_login(self):
        resp = self.client.post(
            reverse("accounts:signup"),
            {"username": "newbie", "email": "", "password1": STRONG_PW, "password2": STRONG_PW},
        )
        self.assertRedirects(resp, reverse("home"))
        self.assertTrue(User.objects.filter(username="newbie").exists())
        # SignupView.form_valid 가 자동 로그인 처리
        self.assertIn("_auth_user_id", self.client.session)

    def test_signup_password_mismatch_rejected(self):
        resp = self.client.post(
            reverse("accounts:signup"),
            {"username": "bad", "email": "", "password1": STRONG_PW, "password2": "different-xyz"},
        )
        self.assertEqual(resp.status_code, 200)  # 폼 오류로 재표시
        self.assertFalse(User.objects.filter(username="bad").exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password=STRONG_PW)

    def test_login_creates_session(self):
        resp = self.client.post(
            reverse("accounts:login"), {"username": "u1", "password": STRONG_PW}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_wrong_password_fails(self):
        resp = self.client.post(
            reverse("accounts:login"), {"username": "u1", "password": "wrong-pw-000"}
        )
        self.assertEqual(resp.status_code, 200)  # 오류 폼 재표시
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_clears_session(self):
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:logout"))  # Django 5 LogoutView = POST
        self.assertNotIn("_auth_user_id", self.client.session)


class AccessControlTests(TestCase):
    def test_protected_url_redirects_to_login(self):
        resp = self.client.get(reverse("problems:list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp.url)

    def test_normal_user_denied_adminpanel(self):
        User.objects.create_user(username="student", password=STRONG_PW)
        self.client.login(username="student", password=STRONG_PW)
        resp = self.client.get(reverse("adminpanel:dashboard"))
        # AdminOnlyMixin: 인증됐지만 권한 없음 → PermissionDenied(403)
        self.assertNotEqual(resp.status_code, 200)

    def test_service_admin_allowed_adminpanel(self):
        User.objects.create_user(username="boss", password=STRONG_PW, role="admin")
        self.client.login(username="boss", password=STRONG_PW)
        resp = self.client.get(reverse("adminpanel:dashboard"))
        self.assertEqual(resp.status_code, 200)
