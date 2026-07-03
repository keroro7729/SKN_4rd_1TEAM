"""사용자 코드 실행/채점 (스캐폴딩).

Docker sandbox 내부에서 Python 3.11 코드를 격리 실행한다.
- Timeout, 표준출력/에러 캡처
- 판정: TestCase.compare_mode (기본 line_trim, LF 정규화, 대소문자 구분)
실제 sandbox 격리(네트워크 차단/메모리 제한)는 Docker 레벨에서 적용.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from config import CODE_TIMEOUT_SEC


def run_code(code: str, stdin_data: str = "", timeout: int = CODE_TIMEOUT_SEC) -> dict:
    """사용자 코드를 별도 프로세스로 실행하고 결과를 반환한다."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "solution.py"
        src.write_text(code, encoding="utf-8")
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
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "", "returncode": None, "timed_out": True}


def normalize(text: str) -> str:
    """LF 정규화 + 라인별 끝 공백 제거."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).rstrip("\n")


def compare_output(expected: str, actual: str, mode: str = "line_trim") -> bool:
    """채점 비교. 기본 line_trim. (float_tolerance는 STEP-04에서 확장)"""
    if mode == "float_tolerance":
        # TODO(STEP-04): 부동소수 허용 오차 비교
        pass
    return normalize(expected) == normalize(actual)
