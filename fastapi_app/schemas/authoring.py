"""테스트케이스 생성 에이전트 스키마 (/ai/authoring/*)."""
from typing import List, Optional

from pydantic import BaseModel

from schemas.common import InternalResponse, LLMStatus


class AuthoringGenerateRequest(BaseModel):
    user_id: Optional[int] = None
    problem_id: Optional[int] = None
    title: str
    description: str
    constraints: str = ""


class AuthoringGenerateResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    solution_code: str = ""      # 정답(레퍼런스) 코드: stdin -> stdout
    generator_code: str = ""     # 랜덤 small 입력 생성기: stdin 의 seed -> 입력 1개 출력
    edge_inputs: List[str] = []  # 엣지 케이스 입력 (1~5)
    time_inputs: List[str] = []  # 시간 측정용(큰) 입력 (1~5)
    notes: str = ""


class AuthoringFixRequest(BaseModel):
    user_id: Optional[int] = None
    problem_id: Optional[int] = None
    title: str = ""
    description: str = ""
    constraints: str = ""
    solution_code: str
    error: str                   # 실행 시 발생한 오류/불일치 메시지
    sample_input: str = ""


class AuthoringFixResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    solution_code: str = ""
    notes: str = ""
