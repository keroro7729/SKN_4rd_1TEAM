"""FastAPI-backed read-only vector diagnostics helpers."""
from __future__ import annotations

import json
import socket
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from django.conf import settings


@dataclass(frozen=True)
class VectorDiagnosticsResult:
    ok: bool
    status: str
    request_id: str
    message: str
    data: dict[str, Any]
    http_status: int | None = None


def call_vector_diagnostics(timeout: float | None = None) -> VectorDiagnosticsResult:
    request_id = uuid.uuid4().hex
    url = f"{settings.FASTAPI_BASE_URL}/ai/diagnostics/chroma"
    timeout = timeout or getattr(settings, "INTERNAL_API_TIMEOUT_SEC", 20)
    api_key = getattr(settings, "INTERNAL_API_KEY", "")
    if not api_key:
        return VectorDiagnosticsResult(
            ok=False,
            status="failed",
            request_id=request_id,
            message="INTERNAL_API_KEY is empty",
            data={},
        )

    req = request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Internal-API-Key": api_key,
            "X-Request-ID": request_id,
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body)
            return VectorDiagnosticsResult(
                ok=payload.get("status") in {"success", "empty"},
                status=str(payload.get("status", "failed")),
                request_id=str(payload.get("request_id", request_id)),
                message=str(payload.get("message", "")),
                data=payload.get("data") or {},
                http_status=response.status,
            )
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return VectorDiagnosticsResult(
            ok=False,
            status="failed",
            request_id=request_id,
            message=f"HTTP {exc.code}: {body[:300]}",
            data={},
            http_status=exc.code,
        )
    except (error.URLError, socket.timeout, TimeoutError) as exc:
        return VectorDiagnosticsResult(
            ok=False,
            status=(
                "timeout"
                if isinstance(exc, (socket.timeout, TimeoutError))
                else "failed"
            ),
            request_id=request_id,
            message=f"{exc.__class__.__name__}: {exc}",
            data={},
        )
    except json.JSONDecodeError as exc:
        return VectorDiagnosticsResult(
            ok=False,
            status="failed",
            request_id=request_id,
            message=f"invalid_json_response: {exc}",
            data={},
        )
