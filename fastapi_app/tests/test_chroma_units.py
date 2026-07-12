"""RAG 청킹 순수 함수 단위 테스트.

services.chroma 는 chromadb 를 import 하므로, 미설치 환경에서는 자동 skip.
"""
import pytest

pytest.importorskip("chromadb")  # 의존성 없으면 이 모듈 전체 skip

from services import chroma  # noqa: E402
import config  # noqa: E402


def test_chunk_text_respects_max_chars():
    long_text = "가나다라마바사아자차. " * 40
    chunks = list(chroma.chunk_text(long_text))
    assert chunks
    assert all(len(c) <= config.RAG_CHUNK_MAX_CHARS for c in chunks)


def test_chunk_text_empty_returns_nothing():
    assert list(chroma.chunk_text("")) == []
