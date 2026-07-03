"""WOOK'S CODING - Worker 로깅 설정.

출력: logs/worker/app.log (회전 파일) + 콘솔.
설계 상세: llm_wiki/5. WOOKS_CODING_로깅_시스템_v0.1.md
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import config

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP = 5


def setup_logging() -> logging.Logger:
    """worker 로거를 구성해 반환한다."""
    (config.LOG_DIR / "worker").mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] worker: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file = RotatingFileHandler(
        config.LOG_DIR / "worker" / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP,
        encoding="utf-8",
    )
    file.setFormatter(fmt)

    logger = logging.getLogger("worker")
    logger.setLevel(config.LOG_LEVEL)
    if not logger.handlers:  # 중복 부착 방지
        logger.addHandler(console)
        logger.addHandler(file)
    logger.propagate = False
    return logger
