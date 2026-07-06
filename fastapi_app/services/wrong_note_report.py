"""오답노트 AI 리포트 - 2단계 RAG 에이전트 (실제 OpenAI + ChromaDB).

설계: llm_wiki/9. WOOKS_CODING_오답노트_AI리포트_useflow_및_RAG설계_v0.1.md §4
FastAPI(Chroma + LLM) 도메인에 격리 구현 — Django/프론트 변경 없음.

흐름:
  ① 1차 리트리빙  : chroma.search(user_id, query=회고)              → similar1
  ② AI 코멘트 생성: LLM(문제 + 제출코드 + 회고 + similar1)
  ③ 최종 리트리빙 : chroma.search(user_id, query=회고+리포트 enriched) → similar2
"""
from __future__ import annotations

import json
import logging
from typing import List

from openai import AsyncOpenAI, OpenAIError

import config
from schemas.common import Evidence
from services import chroma

log = logging.getLogger("ai_research")


class ReportError(RuntimeError):
    """리포트 생성 실패(키 미설정/LLM 오류/파싱 실패)."""


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise ReportError("OPENAI_API_KEY 가 설정되지 않았습니다.")
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


_SYSTEM = (
    "You are a programming-education coach for a Korean coding-practice service. "
    "Given a learner's failed submission and their self-retrospection, you write a "
    "concise, constructive report in KOREAN. You never reveal a full solution; you "
    "guide the learner's thinking. Reply ONLY with a single JSON object."
)


def _prompt(p: dict, similar: List[Evidence]) -> str:
    sim = "\n".join(f"- {e.title or ''} (score {e.score})" for e in similar) or "(없음)"
    return f"""문제: {p.get('problem_title', '')} (난이도 {p.get('difficulty', '')})
태그: {', '.join(p.get('tags', []))}
제출 결과: {p.get('result', '')}   오류 메시지: {p.get('error_message', '')}
제출 코드:
```
{p.get('submitted_code', '')}
```
사용자 회고:
{p.get('user_comment', '') or '(작성하지 않음)'}

과거 유사 오답노트(참고용):
{sim}

아래 키를 가진 JSON 객체로만 답하라(모든 값은 한국어):
- "retrospection_feedback": string — 사용자의 회고에 대한 코치 피드백(정답 직접 노출 금지).
- "missed_points": string[] — 코드/접근에서 놓친 부분 1~4개.
- "learning_direction": string[] — 다음에 학습/연습할 개념·유형 1~4개.
- "summary": object — {{"problem_core": string, "cause": string}} 문제 핵심과 오답 원인 요약.
Output valid JSON only."""


def _as_list(value) -> list[str]:
    return [str(v) for v in value][:5] if isinstance(value, list) else []


async def _llm_report(p: dict, similar: List[Evidence]) -> dict:
    try:
        resp = await _get_client().chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _prompt(p, similar)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except OpenAIError as exc:
        raise ReportError(f"OpenAI 호출 실패: {exc}") from exc
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError as exc:
        raise ReportError(f"LLM JSON 파싱 실패: {exc}") from exc
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "retrospection_feedback": str(data.get("retrospection_feedback") or ""),
        "missed_points": _as_list(data.get("missed_points")),
        "learning_direction": _as_list(data.get("learning_direction")),
        "summary": {
            "problem_core": str(summary.get("problem_core", "")),
            "cause": str(summary.get("cause", "")),
        },
    }


def _dedupe_self(evidence: List[Evidence], self_id) -> List[Evidence]:
    if self_id is None:
        return evidence
    return [e for e in evidence if e.note_id != int(self_id)]


async def generate_report(payload: dict) -> dict:
    """2단계 RAG: 회고기반 1차 검색 → AI 코멘트 → enriched 최종 검색."""
    user_id = int(payload["user_id"])
    self_id = payload.get("wrong_note_id")
    comment = (payload.get("user_comment") or "").strip()

    # ① 1차 리트리빙 (증상: 회고)
    q1 = comment or f"{payload.get('problem_title', '')} {' '.join(payload.get('tags', []))}"
    similar1 = _dedupe_self(chroma.search_user_notes(user_id, q1), self_id)

    # ② AI 코멘트 생성
    report = await _llm_report(payload, similar1)

    # ③ 최종 리트리빙 (진단까지 포함한 enriched 쿼리)
    enriched = " ".join(
        [comment, *report["missed_points"], *report["learning_direction"], report["summary"].get("cause", "")]
    ).strip()
    similar2 = _dedupe_self(chroma.search_user_notes(user_id, enriched or q1), self_id)

    return {"report": report, "stage1_evidence": similar1, "stage2_evidence": similar2}
