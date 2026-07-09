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
    "You are an internal assessment engine and long-term MEMORY for a Korean "
    "coding-practice service. You receive aggregated statistics AND raw signals of a "
    "learner (recent submitted code, questions they asked the tutor, and their "
    "wrong-note retrospections), PLUS your own previous summary/thinking notes. "
    "Infer not only their ability but HOW THEY THINK and debug. "
    "This output is INTERNAL — referenced by other AI features (hints, tutor, "
    "wrong-note analysis) and NEVER shown to the user. "
    "Rules: (1) This is rolling memory — update the previous notes with what CHANGED; "
    "do not rewrite from scratch, and keep consistent wording for persistent traits. "
    "(2) Ground every claim in the given signals; cite the evidence briefly. "
    "(3) If data is sparse, say so plainly and do NOT exaggerate. "
    "Reply ONLY with a JSON object; all values in KOREAN."
)


def _as_list(value) -> list[str]:
    return [str(v) for v in value][:8] if isinstance(value, list) else []


async def summarize(stats: dict) -> dict:
    user = f"""학습자 신호(집계 통계 + 최근 코드/질문/오답 회고 + 직전 메모리), JSON:
{json.dumps(stats, ensure_ascii=False)}

`previous_summary` / `previous_thinking` 는 직전에 네가 남긴 메모리다. 이를 이어받아
**변화점 위주로 갱신**하라(처음부터 새로 쓰지 말 것). 새 근거가 없으면 기존 진단을 유지한다.
`recent_code`·`recent_questions`·`retrospections` 를 근거로 사고 방식을 추론하라.

아래 키를 가진 JSON 객체로만 답하라(모두 한국어):
- "summary": 2~4문장. 코딩 실력·학습 상태를 진단적으로 요약(직전 대비 변화 우선).
- "thinking_profile": 2~4문장. 제출 코드·질문·회고를 근거로 이 학습자가 **어떻게 사고/디버깅하는지**
  (가설을 세우는 방식, 자주 막히는 지점, 개념 공백, 접근 습관)를 서술하고 근거를 짧게 인용.
- "level": "입문" / "초급" / "중급" / "고급" 중 하나.
- "strengths": string[] 강한 알고리즘/유형.
- "weaknesses": string[] 약한 알고리즘/유형.
- "recurring_mistakes": string[] 반복되는 실수 패턴.
- "recommended_focus": string[] 다음에 집중할 학습 주제.
데이터가 적으면 과장하지 말고 summary 에 그 사실을 반영하라. Output valid JSON only."""
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
        "thinking_profile": str(data.get("thinking_profile") or ""),
        "level": str(data.get("level") or ""),
        "strengths": _as_list(data.get("strengths")),
        "weaknesses": _as_list(data.get("weaknesses")),
        "recurring_mistakes": _as_list(data.get("recurring_mistakes")),
        "recommended_focus": _as_list(data.get("recommended_focus")),
        "model": config.OPENAI_MODEL,
    }
