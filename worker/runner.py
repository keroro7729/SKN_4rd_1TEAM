"""사용자 코드 실행/채점 (STEP-04 + 샌드박스 하드닝).

Docker Worker 컨테이너 안에서 Python 3.11 코드를 subprocess 로 실행한다.
- run_code: timeout·표준출력/에러·실행시간(ms) 캡처 + 리소스/네트워크/파일 제한
- compare_output: TestCase.compare_mode 별 비교 (exact / line_trim / float)

샌드박스(.env 로 제어):
- 메모리: RLIMIT_AS = CODE_MEM_LIMIT_MB
- CPU:    RLIMIT_CPU = CODE_TIMEOUT_SEC(+1)
- 파일쓰기 차단: RLIMIT_FSIZE = 0 (디스크 파일 생성/확장 불가, stdout 파이프는 영향 없음)
- 네트워크 차단: socket 무력화(상시) + unshare -rn(지원 환경). 시작 시 가용성 1회 탐지.
"""
import logging
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import config

_log = logging.getLogger("worker")
_MEM_BYTES = config.CODE_MEM_LIMIT_MB * 1024 * 1024


def limit_text(value, limit: int) -> str:
    """DB 저장용으로 UTF-8 문자열을 잘라 반환."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[:limit]


def _apply_limits():
    """자식 프로세스(exec 직전)에 리소스 상한을 건다 (Linux 전용)."""
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_BYTES, _MEM_BYTES))      # 메모리
    cpu = config.CODE_TIMEOUT_SEC + 1
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))                   # CPU 초
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))                    # 파일 쓰기 차단


def _detect_network_isolation() -> bool:
    """unshare -rn 로 네트워크 네임스페이스 격리가 가능한지 1회 탐지."""
    if not config.CODE_DISABLE_NETWORK:
        return False
    if not shutil.which("unshare"):
        _log.warning("unshare 미설치 → 코드 실행 네트워크 격리 비활성 (util-linux 필요)")
        return False
    try:
        r = subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return True
        _log.warning("unshare -rn 사용 불가(rc=%s) → 네임스페이스 격리 비활성(socket 차단은 유지)", r.returncode)
        return False
    except Exception as exc:  # noqa: BLE001
        _log.warning("네트워크 격리 탐지 실패: %s → 비활성", exc)
        return False


_NET_ISOLATED = _detect_network_isolation()

# 이식성 있는 네트워크 차단: 사용자 코드 실행 전에 socket 을 무력화한다.
# (unshare 네임스페이스가 불가한 환경의 상시 방어층. solution.py 는 별도 파일이라 에러 라인번호 보존)
_BOOTSTRAP = '''import runpy, socket
def _blocked(*a, **k):
    raise OSError("network disabled by sandbox")
# 연결/DNS 경로만 차단(소켓 클래스는 서브클래스로 유지 → isinstance 등 라이브러리 호환)
socket.getaddrinfo = _blocked
socket.create_connection = _blocked
_Orig = socket.socket
class _NoNet(_Orig):
    def connect(self, *a, **k): raise OSError("network disabled by sandbox")
    def connect_ex(self, *a, **k): raise OSError("network disabled by sandbox")
socket.socket = _NoNet
runpy.run_path("solution.py", run_name="__main__")
'''


def network_isolated() -> bool:
    """unshare 네임스페이스 격리 활성 여부(soft한 socket 차단은 항상 적용)."""
    return _NET_ISOLATED


def run_code(code: str, stdin_data: str = "", timeout: float = None) -> dict:
    """사용자 코드를 격리된 별도 프로세스로 실행하고 결과를 반환한다."""
    timeout = timeout or config.CODE_TIMEOUT_SEC
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "solution.py").write_text(code, encoding="utf-8")
        (Path(tmp) / "_sandbox.py").write_text(_BOOTSTRAP, encoding="utf-8")

        argv = [sys.executable, "_sandbox.py"]
        if _NET_ISOLATED:  # 지원 환경: 네트워크 네임스페이스로 강하게 격리
            argv = ["unshare", "-rn", *argv]

        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                preexec_fn=_apply_limits,  # 자식에 메모리/CPU/파일쓰기 제한
            )
            return {
                "stdout": limit_text(proc.stdout, config.STDOUT_LIMIT),
                "stderr": limit_text(proc.stderr, config.STDERR_LIMIT),
                "returncode": proc.returncode,
                "timed_out": False,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "stdout": limit_text(exc.stdout, config.STDOUT_LIMIT),
                "stderr": limit_text(exc.stderr, config.STDERR_LIMIT),
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
    """채점 비교 (지시문 §9.5)."""
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
