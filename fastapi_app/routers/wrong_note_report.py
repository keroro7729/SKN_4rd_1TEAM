"""오답노트 AI 리포트 API (POST /ai/wrong-note/report).

기존 wrong_note 라우터를 건드리지 않도록 별도 파일로 분리(변경영향 최소화).

⚠️ 상태(2026-07): 구현 완료 + main.py 등록되어 동작하나, **아직 Django(ai_proxy)에서
호출되지 않는 미배선(백로그) 엔드포인트**다. 2단계 RAG 리포트(요구사항 FR-RAG-004)의
웹 UI 배선은 향후 작업. 삭제하지 말 것 — 기능은 완성되어 있고 배선만 남았다.
"""
from fastapi import APIRouter, Depends

from logging_setup import log_ai_event
from schemas.common import LLMStatus
from schemas.wrong_note_report import WrongNoteReportRequest, WrongNoteReportResponse
from services import wrong_note_report
from services.security import verify_internal

router = APIRouter(prefix="/ai/wrong-note", tags=["wrong-note"])


@router.post("/report", response_model=WrongNoteReportResponse)
async def report(req: WrongNoteReportRequest, ctx=Depends(verify_internal)):
    """2단계 RAG 오답노트 리포트: 회고기반 검색 → AI 코멘트 → 전체기반 최종 검색."""
    rid = ctx["request_id"]
    try:
        out = await wrong_note_report.generate_report(req.model_dump())
    except wrong_note_report.ReportError as exc:
        return WrongNoteReportResponse(request_id=rid, status=LLMStatus.failed, message=str(exc))

    log_ai_event(
        "wrong_note_report",
        user_id=req.user_id,
        stage1=len(out["stage1_evidence"]),
        stage2=len(out["stage2_evidence"]),
        model=None,
    )
    return WrongNoteReportResponse(
        request_id=rid,
        status=LLMStatus.success,
        report=out["report"],
        stage1_evidence=out["stage1_evidence"],
        stage2_evidence=out["stage2_evidence"],
    )
