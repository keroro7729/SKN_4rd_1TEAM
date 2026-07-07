"""오답노트 AI 리포트 API (POST /ai/wrong-note/report).

기존 wrong_note 라우터를 건드리지 않도록 별도 파일로 분리(변경영향 최소화).
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
