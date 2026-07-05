import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from logs.models import LLMRequestLog

from .client import AIProxyResult, call_fastapi


class FakeHTTPResponse:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class AIProxyClientTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ai-proxy-user",
            password="pass12345",
        )

    @patch("ai_proxy.client.urllib.request.urlopen")
    def test_call_fastapi_logs_success_and_normalizes_response(self, mock_urlopen):
        def echo_request_id(request, timeout=None):
            headers = {key.lower(): value for key, value in request.header_items()}
            return FakeHTTPResponse(
                {
                    "status": "success",
                    "request_id": headers["x-request-id"],
                    "content": "hint text",
                }
            )

        mock_urlopen.side_effect = echo_request_id

        result = call_fastapi(
            user=self.user,
            request_type="hint",
            path="/ai/hint",
            payload={"user_id": self.user.id, "problem_id": 1, "hint_level": 1},
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.data["content"], "hint text")
        log = LLMRequestLog.objects.get(request_type="hint")
        self.assertEqual(log.status, "success")
        self.assertEqual(log.request_id, result.request_id)


class AIProxyViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ai-proxy-view-user",
            password="pass12345",
        )
        self.client.force_login(self.user)

    @patch("ai_proxy.views.call_fastapi")
    def test_hint_endpoint_returns_fixed_json_contract(self, mock_call):
        mock_call.return_value = AIProxyResult(
            status="success",
            request_id="req-1",
            message="success",
            data={"content": "hint text", "hint_level": 1},
        )

        response = self.client.post(
            reverse("ai_proxy:hint"),
            data=json.dumps({"problem_id": 1, "hint_level": 1, "user_code": "print(1)"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["request_id"], "req-1")
        self.assertEqual(body["data"]["content"], "hint text")
        sent_payload = mock_call.call_args.kwargs["payload"]
        self.assertEqual(sent_payload["user_id"], self.user.id)
