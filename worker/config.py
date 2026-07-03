"""Worker 설정. 루트 통합 .env 로드."""
from pathlib import Path
import os

from dotenv import load_dotenv

# worker/config.py -> parents[1] = 레포 루트
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# --- PostgreSQL (jobs polling) ---
DB_CONFIG = {
    "dbname": os.environ.get("POSTGRES_DB", "wooks_coding"),
    "user": os.environ.get("POSTGRES_USER", "wooks"),
    "password": os.environ.get("POSTGRES_PASSWORD", "password"),
    "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
}

# --- 실행 제한 (지시문 §3 확정 기준) ---
CODE_TIMEOUT_SEC = int(os.environ.get("CODE_TIMEOUT_SEC", "5"))
POLL_INTERVAL_SEC = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", "2"))

# --- 로깅 (개발/디버깅) ---
# LOG_DIR 이 비면 <repo루트>/logs. Docker 는 compose 가 /app/logs 주입.
LOG_DIR = Path(os.environ.get("LOG_DIR") or (ROOT / "logs"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
