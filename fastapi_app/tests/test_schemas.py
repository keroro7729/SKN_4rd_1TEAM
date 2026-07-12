"""요청 스키마 검증 테스트 (pydantic, 외부 의존 없음)."""
import pytest
from pydantic import ValidationError

from schemas.wrong_note import WrongNoteAnalyzeRequest, WrongNoteEmbedRequest


def test_analyze_request_requires_user_id():
    with pytest.raises(ValidationError):
        WrongNoteAnalyzeRequest(comment="회고")  # user_id 필수


def test_analyze_request_defaults():
    req = WrongNoteAnalyzeRequest(user_id=1)
    assert req.tags == []
    assert req.code == ""
    assert req.coding_state == ""


def test_embed_request_requires_wrong_note_id():
    with pytest.raises(ValidationError):
        WrongNoteEmbedRequest(user_id=1)  # wrong_note_id 필수
