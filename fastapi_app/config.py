"""FastAPI AI/RAG 서버 설정. 루트 통합 .env 로드."""
from pathlib import Path
import os

from dotenv import load_dotenv

# fastapi_app/config.py -> parents[1] = 레포 루트
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# --- 내부 통신 보안 (Django -> FastAPI) ---
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")

# --- OpenAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# --- ChromaDB (벡터 검색 인덱스) ---
CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
# MVP는 wrong_note_embeddings 컬렉션만 생성 (concept/pattern 제외)
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "wrong_note_embeddings")

# --- RAG 기본값 (지시문 §3 확정 기준) ---
RAG_SCORE_THRESHOLD = float(os.environ.get("RAG_SCORE_THRESHOLD", "0.35"))
RAG_TOP_K = int(os.environ.get("TOP_K", "5"))
