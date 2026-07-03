# worker/sandbox

사용자 코드가 **격리 실행**되는 런타임 영역입니다.

- 베이스 이미지: `python:3.11-slim` (문서 규칙: 실행 언어는 Python 3.11 한정)
- 격리 기준(STEP-04/11에서 강화):
  - **Timeout**: `CODE_TIMEOUT_SEC=5`
  - **네트워크 차단**: 컨테이너 `network_mode: none` 또는 별도 격리 네트워크
  - **메모리 제한**: `--memory` 제한
  - **비root 실행**: 전용 unprivileged 유저

현재는 스캐폴딩 단계로, 실제 실행 로직은 `worker/runner.py`의 `run_code()`에 있습니다.
