"""코딩 상태 요약 - 실제 OpenAI.

Django 가 집계한 학습 통계를 받아, 학습자의 코딩 실력/학습 상태를 추론한다.
결과는 사용자에게 보이지 않는 AI 내부 참고값(다른 AI 기능이 프롬프트에 주입).
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI, OpenAIError

import config

log = logging.getLogger("ai_research")


class CodingStateError(RuntimeError):
    pass


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise CodingStateError("OPENAI_API_KEY 가 설정되지 않았습니다.")
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


_SYSTEM = (
    "You are an internal assessment engine for a Korean coding-practice service. "
    "Given aggregated statistics about a learner, infer their coding ability and "
    "learning state. This output is INTERNAL — it is referenced by other AI features "
    "(hints, wrong-note analysis) and is NEVER shown to the user. Be candid and "
    "diagnostic. Reply ONLY with a JSON object; all values in KOREAN."
)


def _as_list(value) -> list[str]:
    return [str(v) for v in value][:8] if isinstance(value, list) else []


async def summarize(stats: dict) -> dict:
    user = f"""학습자 집계 통계(JSON):
{json.dumps(stats, ensure_ascii=False)}

위 통계를 근거로 아래 키를 가진 JSON 객체로만 답하라(모두 한국어):
- "summary": 2~4문장. 이 학습자의 코딩 실력과 학습 상태를 진단적으로 요약(AI 참고용).
- "level": "입문" / "초급" / "중급" / "고급" 중 추정 수준 하나.
- "strengths": string[] 강한 알고리즘/유형 (근거 기반, 없으면 빈 배열).
- "weaknesses": string[] 약한 알고리즘/유형.
- "recurring_mistakes": string[] 반복되는 실수 패턴.
- "recommended_focus": string[] 다음에 집중해야 할 학습 주제.
데이터가 적으면 과장하지 말고 그 사실을 summary 에 반영하라. Output valid JSON only1."""
    try:
        resp = await _get_client().chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except OpenAIError as exc:
        raise CodingStateError(f"openai_error: {exc}") from exc
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError as exc:
        raise CodingStateError(f"json_parse_error: {exc}") from exc

    log.info(json.dumps({"event": "coding_state", "model": config.OPENAI_MODEL}, ensure_ascii=False))
    return {
        "summary": str(data.get("summary") or ""),
        "level": str(data.get("level") or ""),
        "strengths": _as_list(data.get("strengths")),
        "weaknesses": _as_list(data.get("weaknesses")),
        "recurring_mistakes": _as_list(data.get("recurring_mistakes")),
        "recommended_focus": _as_list(data.get("recommended_focus")),
        "model": config.OPENAI_MODEL,
    }
