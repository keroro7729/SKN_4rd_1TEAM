"""WOOK'S CODING - FastAPI AI/RAG 진입점.

역할: AI 단계별 힌트, 오답노트 분석, 유사 오답노트 RAG 검색, 내 노트 질의응답.
Django(서비스 로직)와 분리된 AI 로직 서버. 실행: uvicorn main:app
"""
from fastapi import FastAPI

import config  # noqa: F401  (.env 로드 트리거)
from logging_setup import setup_logging
from routers import health, hint, wrong_note

# 앱 생성 전에 로깅 초기화 (콘솔 + logs/fastapi/app.log + logs/ai/research.jsonl)
setup_logging()

app = FastAPI(
    title="WOOK'S CODING AI/RAG API",
    version="0.1.0",
    description="AI 힌트 · 오답노트 분석 · 오답노트 RAG · 내 노트 질의응답",
)

app.include_router(health.router)
app.include_router(hint.router)
app.include_router(wrong_note.router)
