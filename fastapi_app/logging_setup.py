"""WOOK'S CODING - FastAPI 로깅 설정.

두 갈래 로그를 남긴다.
- 일반(개발/디버깅): logs/fastapi/app.log  (회전 파일 + 콘솔)
- AI 연구용:         logs/ai/research.jsonl (LLM/RAG 이벤트를 JSON Lines 로)

설계 상세: llm_wiki/5. WOOKS_CODING_로깅_시스템_v0.1.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

import config

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP = 5
_configured = False


def setup_logging() -> None:
    """root 로거에 콘솔 + 회전 파일 핸들러를 붙인다 (중복 호출 안전)."""
    global _configured
    if _configured:
        return

    (config.LOG_DIR / "fastapi").mkdir(parents=True, exist_ok=True)
    (config.LOG_DIR / "ai").mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    app_file = RotatingFileHandler(
        config.LOG_DIR / "fastapi" / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP,
        encoding="utf-8",
    )
    app_file.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)
    root.addHandler(console)
    root.addHandler(app_file)

    # AI 연구용 로거: 메시지를 그대로(= JSON 한 줄) 기록, 일반 로그와 분리
    ai_file = RotatingFileHandler(
        config.LOG_DIR / "ai" / "research.jsonl",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP,
        encoding="utf-8",
    )
    ai_file.setFormatter(logging.Formatter("%(message)s"))
    ai_logger = logging.getLogger("ai_research")
    ai_logger.setLevel(logging.INFO)
    ai_logger.addHandler(ai_file)
    ai_logger.propagate = False  # app.log 로 새어나가지 않게

    _configured = True
    logging.getLogger(__name__).info("logging initialized (LOG_DIR=%s)", config.LOG_DIR)


def log_ai_event(event: str, **fields) -> None:
    """AI 연구용 구조화 로그 1건 기록 (JSON Lines).

    예) log_ai_event("hint", problem_id=1, hint_level=2, model="gpt-4o-mini")
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logging.getLogger("ai_research").info(json.dumps(record, ensure_ascii=False))
