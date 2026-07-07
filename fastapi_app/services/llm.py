"""OpenAI 연동 (오답노트 분석·내 노트 질의). 힌트는 아직 미구현(스텁).

analyze_wrong_note / answer_from_notes 는 실제 OpenAI 호출.
generate_hint 는 STEP-06 담당 전까지 not_implemented.
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI, OpenAIError

import config
from schemas.common import Evidence

log = logging.getLogger("ai_research")


class LLMNotImplementedError(NotImplementedError):
    """AI 생성 계층이 아직 구현되지 않았을 때(또는 키 미설정)."""


class LLMCallError(RuntimeError):
    """OpenAI 호출/파싱 실패."""


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise LLMNotImplementedError("openai_key_missing")
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


async def _chat_json(system: str, user: str) -> dict:
    try:
        resp = await _get_client().chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except OpenAIError as exc:
        raise LLMCallError(f"openai_error: {exc}") from exc
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError as exc:
        raise LLMCallError(f"json_parse_error: {exc}") from exc


async def generate_hint(problem_id: int, user_code: str, hint_level: int) -> str:
    """1~3단계 힌트 (STEP-06 담당 구현 예정)."""
    raise LLMNotImplementedError("not_implemented")


_ANALYZE_SYSTEM = (
    "You are a Korean coding-education coach. Given a learner's failed submission code "
    "and their self-retrospection, produce a concise, constructive analysis in KOREAN. "
    "Do NOT reveal a full solution; guide the thinking. Reply ONLY with a JSON object."
)


async def analyze_wrong_note(
    code: str, comment: str, evidence: list[Evidence], coding_state: str = ""
) -> dict:
    """오답을 문제핵심/오답원인/풀이과정/주의사항 4섹션으로 분석.

    coding_state: 사용자 코딩 상태(AI 내부 참고값). 있으면 학습자 수준/약점에 맞춰 분석한다.
    """
    ref = ""
    if evidence:
        ref = "\n참고(과거 유사 오답): " + ", ".join(
            f"note {e.note_id}({e.title or ''})" for e in evidence
        )
    ctx = f"\n\n{coding_state}\n(위 상태를 참고해 학습자 수준·약점에 맞춰 분석하되, 이 내용을 사용자에게 그대로 노출하지는 말 것.)" if coding_state else ""
    user = f"""제출 코드:
```
{code or '(코드 없음)'}
```
사용자 회고:
{comment or '(작성하지 않음)'}{ref}{ctx}

아래 키를 가진 JSON 객체로만 답하라(모두 한국어, 정답 직접 노출 금지):
- "problem_core": 이 문제/코드에서 핵심적으로 다뤄야 할 개념 한두 줄.
- "cause": 이 코드가 틀렸을 가능성이 높은 원인.
- "solution": 정답을 직접 주지 말고, 올바른 접근/풀이 과정을 단계적으로 안내.
- "caution": 다음에 같은 실수를 피하기 위한 주의사항.
JSON only."""
    data = await _chat_json(_ANALYZE_SYSTEM, user)
    log.info(json.dumps({"event": "analyze", "model": config.OPENAI_MODEL}, ensure_ascii=False))
    return {
        "problem_core": str(data.get("problem_core") or ""),
        "cause": str(data.get("cause") or ""),
        "solution": str(data.get("solution") or ""),
        "caution": str(data.get("caution") or ""),
    }


_ASK_SYSTEM = (
    "You are a study assistant answering questions about the user's OWN past wrong-note "
    "records. Answer in KOREAN, grounded ONLY in the provided evidence notes; if evidence "
    "is thin, say so honestly. Never fabricate note contents."
)


async def answer_from_notes(question: str, evidence: list[Evidence]) -> str:
    """내 오답노트 근거 기반 자연어 답변 (근거 없는 단정 금지)."""
    ev = "\n".join(
        f"- note_id {e.note_id} ({e.title or ''}) score {e.score}" for e in evidence
    ) or "(근거 노트 없음)"
    user = f"""질문: {question}

근거가 되는 내 오답노트 목록:
{ev}

위 근거를 바탕으로 한국어로 답하라. 근거가 부족하면 솔직히 밝혀라.
JSON 객체 {{"answer": string}} 형태로만 답하라."""
    data = await _chat_json(_ASK_SYSTEM, user)
    return str(data.get("answer") or "")
