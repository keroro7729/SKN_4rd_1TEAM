"""사용자 코드 실행/채점 (STEP-04 + 샌드박스 하드닝).

Docker Worker 컨테이너 안에서 Python 3.11 코드를 subprocess 로 실행한다.
- run_code: timeout·표준출력/에러·실행시간(ms) 캡처 + 리소스/네트워크/파일 제한
- compare_output: TestCase.compare_mode 별 비교 (exact / line_trim / float)
- judge: 여러 테스트케이스로 최종 판정 → Submission.result / ExecutionJob.status 매핑

샌드박스(.env 로 제어):
- 메모리: RLIMIT_AS = CODE_MEM_LIMIT_MB
- CPU:    RLIMIT_CPU = CODE_TIMEOUT_SEC(+1)
- 파일쓰기 차단: RLIMIT_FSIZE = 0 (디스크 파일 생성/확장 불가, stdout 파이프는 영향 없음)
- 네트워크 차단: unshare -rn (user+net 네임스페이스). 시작 시 가용성 1회 탐지, 불가하면 경고.
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
        r = subprocess.run(
            ["unshare", "-rn", "true"], capture_output=True, timeout=5
        )
        if r.returncode == 0:
            return True
        _log.warning("unshare -rn 사용 불가(rc=%s) → 네트워크 격리 비활성", r.returncode)
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


def run_code(code: str, stdin_data: str = "", timeout: int = None) -> dict:
    """사용자 코드를 격리된 별도 프로세스로 실행하고 결과를 반환한다."""
    timeout = timeout or config.CODE_TIMEOUT_SEC
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "solution.py").write_text(code, encoding="utf-8")
        (Path(tmp) / "_sandbox.py").write_text(_BOOTSTRAP, encoding="utf-8")

        argv = [sys.executable, "_sandbox.py"]
        if _NET_ISOLATED:  # 지원 환경: 네트워크 네임스페이스로 강하게 격리
            argv = ["unshare", "-rn", *argv]

        start = time.perf_counter()
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
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "timed_out": False,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "",
                "returncode": None,
                "timed_out": True,
                "elapsed_ms": int(timeout * 1000),
            }


def _lf(text: str) -> str:
    """CRLF/CR → LF 정규화."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def normalize(text: str) -> str:
    """line_trim: LF 정규화 + 라인별 끝 공백 제거 + 마지막 개행 제거."""
    return "\n".join(line.rstrip() for line in _lf(text).split("\n")).rstrip("\n")


def _compare_float(expected: str, actual: str, tol: float) -> bool:
    """토큰 단위 부동소수 허용 오차 비교. 숫자가 아니면 문자열 일치로 비교."""
    e_tokens, a_tokens = _lf(expected).split(), _lf(actual).split()
    if len(e_tokens) != len(a_tokens):
        return False
    for x, y in zip(e_tokens, a_tokens):
        try:
            if abs(float(x) - float(y)) > tol:
                return False
        except ValueError:
            if x != y:
                return False
    return True


def compare_output(
    expected: str, actual: str, mode: str = "line_trim", float_tolerance: float = 1e-6
) -> bool:
    """채점 비교 (지시문 §9.5). 기본 line_trim, 대소문자 구분."""
    if mode == "float":
        return _compare_float(expected, actual, float_tolerance)
    if mode == "exact":  # CRLF만 LF로 변환, 공백은 그대로 (마지막 개행만 무시)
        return _lf(expected).rstrip("\n") == _lf(actual).rstrip("\n")
    return normalize(expected) == normalize(actual)  # line_trim (default)


def judge(code: str, test_cases: list, timeout: int = None) -> dict:
    """여러 테스트케이스로 코드를 채점한다.

    test_cases: [{input_data, expected_output, compare_mode, float_tolerance}, ...]
    반환: {result, job_status, output, error_message, elapsed_ms, passed, total}

    상태 매핑(지시문 §9.4):
      - timeout            → result=timeout, job_status=timeout
      - 사용자 코드 오류   → result=error,   job_status=success (job 자체는 정상 수행)
      - 오답               → result=wrong,   job_status=success
      - 전부 통과          → result=success, job_status=success
    """
    total = len(test_cases)
    # 테스트케이스가 없으면(미seed) 실행 가능 여부만 1회 확인한다.
    cases = test_cases or [{"input_data": "", "expected_output": None}]
    max_ms = 0
    passed = 0
    first_output = ""

    for i, tc in enumerate(cases):
        res = run_code(code, tc.get("input_data") or "", timeout)
        max_ms = max(max_ms, res["elapsed_ms"])

        if res["timed_out"]:
            return _verdict("timeout", "timeout", first_output, "", max_ms, passed, total)
        if res["returncode"] != 0:  # 사용자 코드 런타임/문법 오류
            return _verdict("error", "success", res["stdout"], res["stderr"], max_ms, passed, total)
        if i == 0:
            first_output = res["stdout"]

        expected = tc.get("expected_output")
        if expected is None:  # 채점 기준 없음 → 실행 성공만 인정
            passed += 1
            continue
        if compare_output(
            expected, res["stdout"], tc.get("compare_mode", "line_trim"),
            tc.get("float_tolerance", 1e-6),
        ):
            passed += 1
        else:
            return _verdict("wrong", "success", res["stdout"], "", max_ms, passed, total)

    return _verdict("success", "success", first_output, "", max_ms, passed, total)


def _verdict(result, job_status, output, error_message, elapsed_ms, passed, total) -> dict:
    return {
        "result": result,
        "job_status": job_status,
        "output": output or "",
        "error_message": error_message or "",
        "elapsed_ms": elapsed_ms,
        "passed": passed,
        "total": total,
    }
