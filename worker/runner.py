"""사용자 코드 실행/채점 (스캐폴딩).

Docker sandbox 내부에서 Python 3.11 코드를 격리 실행한다.
- Timeout, 표준출력/에러 캡처
- 판정: TestCase.compare_mode (기본 line_trim, LF 정규화, 대소문자 구분)
실제 sandbox 격리(네트워크 차단/메모리 제한)는 Docker 레벨에서 적용.
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from config import CODE_TIMEOUT_SEC, STDERR_LIMIT, STDOUT_LIMIT


def limit_text(value, limit: int) -> str:
    """Return a UTF-8 string truncated for DB storage."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[:limit]


def run_code(code: str, stdin_data: str = "", timeout: int = CODE_TIMEOUT_SEC) -> dict:
    """사용자 코드를 별도 프로세스로 실행하고 결과를 반환한다."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "solution.py"
        src.write_text(code, encoding="utf-8")
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(src)],
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
            )
            return {
                "stdout": limit_text(proc.stdout, STDOUT_LIMIT),
                "stderr": limit_text(proc.stderr, STDERR_LIMIT),
                "returncode": proc.returncode,
                "timed_out": False,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "stdout": limit_text(exc.stdout, STDOUT_LIMIT),
                "stderr": limit_text(exc.stderr, STDERR_LIMIT),
                "returncode": None,
                "timed_out": True,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }


def normalize(text: str) -> str:
    """LF 정규화 + 라인별 양끝 공백 제거."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.strip() for line in lines).strip("\n")


def compare_output(
    expected: str,
    actual: str,
    mode: str = "line_trim",
    float_tolerance: float = 1e-6,
) -> bool:
    """채점 비교."""
    if mode == "exact":
        return expected == actual
    if mode == "float":
        expected_values = normalize(expected).split()
        actual_values = normalize(actual).split()
        if len(expected_values) != len(actual_values):
            return False
        try:
            return all(
                abs(float(exp) - float(act)) <= float_tolerance
                for exp, act in zip(expected_values, actual_values)
            )
        except ValueError:
            return False
    return normalize(expected) == normalize(actual)
