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
# RAG 임베딩 모델/백엔드. auto=키 있으면 openai, 없으면 결정적 해시(오프라인 폴백).
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
RAG_EMBED_BACKEND = os.environ.get("RAG_EMBED_BACKEND", "auto")  # auto | openai | hash

# --- ChromaDB (벡터 검색 인덱스) ---
CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
# MVP는 wrong_note_embeddings 컬렉션만 생성 (concept/pattern 제외)
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "wrong_note_embeddings")

# --- RAG 기본값 (지시문 §3 확정 기준) ---
RAG_SCORE_THRESHOLD = float(os.environ.get("RAG_SCORE_THRESHOLD", "0.35"))
RAG_TOP_K = int(os.environ.get("TOP_K", "5"))

# --- RAG 리트리빙 고도화(v1: 섹션 단위 멀티 청킹 + mean/max 집계) ---
# 회고·AI코멘트를 짧은 청크로 분리 임베딩, 노이즈(문제 원문/코드/난이도/에러) 제외.
RAG_CHUNK_MAX_CHARS = int(os.environ.get("RAG_CHUNK_MAX_CHARS", "160"))
RAG_PER_QUERY_K = int(os.environ.get("RAG_PER_QUERY_K", "12"))  # 쿼리 청크당 후보 청크 수
RAG_W_MEAN = float(os.environ.get("RAG_W_MEAN", "0.5"))         # 섹션 유사도 평균 가중
RAG_W_MAX = float(os.environ.get("RAG_W_MAX", "0.5"))           # 섹션 유사도 최댓값 가중

# --- 로깅 (개발/디버깅/AI연구용) ---
# LOG_DIR 이 비면 <repo루트>/logs. Docker 는 compose 가 /app/logs 주입.
LOG_DIR = Path(os.environ.get("LOG_DIR") or (ROOT / "logs"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
