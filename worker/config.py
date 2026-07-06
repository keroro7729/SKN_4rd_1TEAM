"""Worker 설정. 루트 통합 .env 로드."""
from pathlib import Path
import os

from dotenv import load_dotenv

# worker/config.py -> parents[1] = 레포 루트
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def env_int(key: str, default: str, minimum: int = 1) -> int:
    value = int(os.environ.get(key, default))
    return max(minimum, value)

# --- PostgreSQL (jobs polling) ---
DB_CONFIG = {
    "dbname": os.environ.get("POSTGRES_DB", "wooks_coding"),
    "user": os.environ.get("POSTGRES_USER", "wooks"),
    "password": os.environ.get("POSTGRES_PASSWORD", "password"),
    "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
}

# --- 실행 제한 / 샌드박스 (지시문 §3 + 하드닝) ---
CODE_TIMEOUT_SEC = env_int("CODE_TIMEOUT_SEC", "5")
MAX_TEST_CASES = env_int("MAX_TEST_CASES", "5")
DEFAULT_TEST_CASES = min(env_int("DEFAULT_TEST_CASES", "1"), MAX_TEST_CASES)
CODE_MEM_LIMIT_MB = env_int("CODE_MEM_LIMIT_MB", "256", minimum=16)
CODE_DISABLE_NETWORK = (os.environ.get("CODE_DISABLE_NETWORK") or "true").lower() in (
    "1", "true", "yes", "on",
)
POLL_INTERVAL_SEC = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", "2"))
STDOUT_LIMIT = env_int("STDOUT_LIMIT", "10000")
STDERR_LIMIT = env_int("STDERR_LIMIT", "10000")

# --- 로깅 (개발/디버깅) ---
# LOG_DIR 이 비면 <repo루트>/logs. Docker 는 compose 가 /app/logs 주입.
LOG_DIR = Path(os.environ.get("LOG_DIR") or (ROOT / "logs"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
