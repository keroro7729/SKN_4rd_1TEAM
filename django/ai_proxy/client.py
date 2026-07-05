"""Internal FastAPI client for Django AI/RAG proxy endpoints."""
from __future__ import annotations

import json
import socket
import traceback
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.utils import timezone

from logs.models import ErrorLog, LLMRequestLog

VALID_STATUSES = {"success", "failed", "timeout", "empty"}
RESPONSE_META_KEYS = {"status", "request_id", "message", "detail"}


@dataclass
class AIProxyResult:
    status: str
    request_id: str
    message: str
    data: dict[str, Any]
    raw: dict[str, Any] | None = None
    error_type: str = ""

    def to_response(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "request_id": self.request_id,
            "message": self.message,
            "data": self.data,
        }


class FastAPIClientError(RuntimeError):
    """Raised when a FastAPI AI/RAG call returns a non-successful status."""

    def __init__(self, result: AIProxyResult):
        super().__init__(result.message)
        self.result = result


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _response_data(raw: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in raw.items() if key not in RESPONSE_META_KEYS}


def _contains_stub(value: Any) -> bool:
    if isinstance(value, str):
        return "[stub]" in value.lower()
    if isinstance(value, dict):
        return any(_contains_stub(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_stub(item) for item in value)
    return False


def _message_from_raw(raw: dict[str, Any], default: str = "") -> str:
    message = raw.get("message") or raw.get("detail") or default
    if isinstance(message, list):
        return _json_dumps(message)
    return str(message or "")


def _log_error(
    *,
    user,
    path: str,
    error_type: str,
    message: str,
    tb: str = "",
):
    source = "chromadb" if "chroma" in f"{error_type} {message}".lower() else "fastapi"
    ErrorLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        source=source,
        level="error",
        path=path,
        error_type=error_type,
        message=message,
        traceback=tb,
    )


def _complete_log(log: LLMRequestLog, result: AIProxyResult):
    log.status = result.status
    log.response_text = _json_dumps(result.raw or result.to_response())
    log.error_type = result.error_type
    log.error_message = "" if result.status in {"success", "empty"} else result.message
    log.completed_at = timezone.now()
    log.save(
        update_fields=[
            "status",
            "response_text",
            "error_type",
            "error_message",
            "completed_at",
        ]
    )


def call_fastapi(
    *,
    user,
    request_type: str,
    path: str,
    payload: dict[str, Any],
    timeout: int | None = None,
    raise_on_error: bool = False,
) -> AIProxyResult:
    """Call FastAPI with internal headers and return the fixed Django JSON contract."""
    request_id = uuid.uuid4().hex
    timeout = timeout or settings.INTERNAL_API_TIMEOUT_SEC
    url = f"{settings.FASTAPI_BASE_URL}{path}"

    log = LLMRequestLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        request_type=request_type,
        request_id=request_id,
        input_text=_json_dumps(payload),
        status="processing",
    )
    error_logged = False

    request = urllib.request.Request(
        url,
        data=_json_dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Internal-API-Key": settings.INTERNAL_API_KEY,
            "X-Request-ID": request_id,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
        raw = json.loads(body or "{}")
        if not isinstance(raw, dict):
            raise ValueError("fastapi_response_not_object")

        status = raw.get("status") or "success"
        if status not in VALID_STATUSES:
            result = AIProxyResult(
                status="failed",
                request_id=raw.get("request_id") or request_id,
                message=f"unsupported FastAPI status: {status}",
                data={},
                raw=raw,
                error_type="ResponseFormatError",
            )
        else:
            error_type = raw.get("error_type") or (
                "FastAPIStatusFailed" if status == "failed" else ""
            )
            result = AIProxyResult(
                status=status,
                request_id=raw.get("request_id") or request_id,
                message=_message_from_raw(raw, default=status),
                data=_response_data(raw),
                raw=raw,
                error_type=error_type,
            )
            if status == "success" and _contains_stub(raw):
                result = AIProxyResult(
                    status="failed",
                    request_id=raw.get("request_id") or request_id,
                    message="not_implemented",
                    data={},
                    raw=raw,
                    error_type="NotImplemented",
                )
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            raw_error = json.loads(error_body or "{}")
        except json.JSONDecodeError:
            raw_error = {"detail": error_body}
        result = AIProxyResult(
            status="failed",
            request_id=request_id,
            message=_message_from_raw(raw_error, default=f"FastAPI HTTP {exc.code}"),
            data={"http_status": exc.code},
            raw=raw_error,
            error_type=f"HTTP_{exc.code}",
        )
        _log_error(
            user=user,
            path=path,
            error_type=result.error_type,
            message=result.message,
        )
        error_logged = True
    except (socket.timeout, TimeoutError) as exc:
        result = AIProxyResult(
            status="timeout",
            request_id=request_id,
            message="FastAPI request timed out.",
            data={},
            error_type=exc.__class__.__name__,
        )
        _log_error(
            user=user,
            path=path,
            error_type=result.error_type,
            message=result.message,
            tb=traceback.format_exc(),
        )
        error_logged = True
    except (urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        result = AIProxyResult(
            status="failed",
            request_id=request_id,
            message=str(exc),
            data={},
            error_type=exc.__class__.__name__,
        )
        _log_error(
            user=user,
            path=path,
            error_type=result.error_type,
            message=result.message,
            tb=traceback.format_exc(),
        )
        error_logged = True

    _complete_log(log, result)
    if result.status in {"failed", "timeout"} and not error_logged:
        _log_error(
            user=user,
            path=path,
            error_type=result.error_type or "FastAPIStatusError",
            message=result.message,
        )
    if raise_on_error and result.status not in {"success", "empty"}:
        raise FastAPIClientError(result)
    return result
