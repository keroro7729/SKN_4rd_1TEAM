"""pytest 공통 설정: fastapi_app 루트를 import 경로에 추가."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # fastapi_app/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
