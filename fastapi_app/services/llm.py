"""OpenAI 연동 (힌트·오답노트 분석·미니튜터 등). 전부 실제 OpenAI 호출."""
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


_HINT_SYSTEM = (
    "You are a Socratic coding tutor for a Korean coding-practice service. You give "
    "STEP-BY-STEP hints tailored to the learner's level. A GOOD hint makes the learner "
    "THINK, WRITE code themselves, and VERIFY — it NEVER reveals the answer, the full "
    "approach, or ready-to-paste solution code. Reply ONLY with a JSON object; the hint "
    "content must be in KOREAN.\n"
    "Style by learner level:\n"
    "- 입문/초급: briefly explain the relevant syntax/concept in plain words, then scaffold "
    "with gentle first-step prompts like 'for문부터 써볼까요?', '주석으로 풀이 계획을 세워볼까요?'.\n"
    "- 중급: do NOT point out the exact bug. Instead teach them to find it themselves — e.g. "
    "print 기반 디버깅으로 중간값을 찍어보게 유도하거나, 다른 접근법/비유를 제시해 개념을 떠올리게 하거나, "
    "'~개념을 공부하고 다시 풀러 와볼까요?' 처럼 스스로 방향을 잡게 한다.\n"
    "- 고급: minimal high-level nudges — point at the class of technique or a property to "
    "reason about, and let the learner drive.\n"
    "Depth by hint_level: 1 = gentlest orientation/concept, 2 = more concrete process "
    "guidance, 3 = most concrete scaffolding (still NOT the full answer or code)."
)


async def generate_hint(
    problem: dict,
    user_code: str,
    hint_level: int,
    coding_state: str = "",
    level: str = "",
) -> str:
    """문제 + 현재 코드 + 사용자 레벨을 반영한 단계별 소크라테스식 힌트.

    problem: {title, description, constraints, difficulty}
    """
    ctx = f"\n\n{coding_state}" if coding_state else ""
    user = f"""문제: {problem.get('title', '')} (난이도 {problem.get('difficulty', '')})
{problem.get('description', '')}
제약조건: {problem.get('constraints', '') or '(명시 없음)'}

학습자가 지금 작성한 코드:
```
{user_code or '(아직 작성하지 않음)'}
```
힌트 단계(hint_level): {hint_level} / 3
학습자 추정 수준: {level or '(미평가)'}{ctx}

위 학습자의 수준과 현재 코드 상태를 고려해, hint_level {hint_level} 에 맞는 힌트를 하나 만들어라.
반드시 지킬 것: 정답·전체 접근법·붙여넣기용 코드 금지. 학습자가 스스로 생각하고, 직접 써보고,
결과를 확인해보게 만드는 힌트여야 한다. (coding_state 내용을 사용자에게 그대로 노출하지 말 것)
JSON 객체 {{"content": string}} 형태로만 답하라(content 는 한국어)."""
    data = await _chat_json(_HINT_SYSTEM, user)
    return str(data.get("content") or "")


_ANALYZE_SYSTEM = (
    "You are a Korean coding-education coach. Given a problem, a learner's failed "
    "submission code, and their self-retrospection, produce a structured, constructive "
    "analysis in KOREAN. Never reveal a full, paste-ready solution; guide the thinking. "
    "Reply ONLY with a single JSON object."
)


async def analyze_wrong_note(
    code: str,
    comment: str,
    evidence: list[Evidence],
    coding_state: str = "",
    problem_title: str = "",
    tags: list[str] | None = None,
    problem_statement: str = "",
) -> dict:
    """오답을 6섹션으로 분석: 문제핵심·풀이과정·오답원인·개선사항·AI피드백·다음체크리스트.

    coding_state: 사용자 코딩 상태(AI 내부 참고값). 있으면 학습자 수준/약점에 맞춰 분석한다.
    """
    tags = tags or []
    ref = ""
    if evidence:
        ref = "\n참고(과거 유사 오답): " + ", ".join(
            f"note {e.note_id}({e.title or ''})" for e in evidence
        )
    ctx = f"\n\n{coding_state}\n(위 상태를 참고해 학습자 수준·약점에 맞춰 분석하되, 이 내용을 사용자에게 그대로 노출하지는 말 것.)" if coding_state else ""
    stmt = (problem_statement or "").strip()
    if len(stmt) > 1500:
        stmt = stmt[:1500] + " …(생략)"
    user = f"""문제: {problem_title or '(제목 없음)'}
태그: {', '.join(tags) or '(없음)'}
문제 설명:
{stmt or '(제공되지 않음)'}

제출 코드:
```
{code or '(코드 없음)'}
```
사용자 회고:
{comment or '(작성하지 않음)'}{ref}{ctx}

아래 키를 가진 JSON 객체로만 답하라(모두 한국어, 붙여넣기용 정답 코드 금지):
- "problem_core": string — 이 문제에서 핵심적으로 이해해야 할 요구사항/개념을 2~3문장으로.
- "solution": string — 이 문제의 정석적인 풀이 접근법을 단계적으로 설명(정답 코드는 직접 주지 말 것).
- "cause": string — 제출 코드에서 잘못된 부분과 오답의 직접적인 원인을 구체적으로 지목.
- "improvement": string — 코드를 구체적으로 어떻게 고쳐서 다시 시도하면 되는지 안내(어느 부분을 어떻게).
- "ai_feedback": string — 학습자의 학습을 개선하기 위한 자유 형식 피드백(격려·학습 방향 등).
- "next_checklist": string[] — 다음 풀이 전에 먼저 점검/생각해야 할 체크리스트 2~4개(자주 하는 실수 위주, 각 항목 짧게).
JSON only."""
    data = await _chat_json(_ANALYZE_SYSTEM, user)
    log.info(json.dumps({"event": "analyze", "model": config.OPENAI_MODEL}, ensure_ascii=False))
    checklist = data.get("next_checklist")
    checklist = [str(x) for x in checklist if str(x).strip()][:4] if isinstance(checklist, list) else []
    return {
        "problem_core": str(data.get("problem_core") or ""),
        "solution": str(data.get("solution") or ""),
        "cause": str(data.get("cause") or ""),
        "improvement": str(data.get("improvement") or ""),
        "ai_feedback": str(data.get("ai_feedback") or ""),
        "next_checklist": checklist,
    }


_TUTOR_SYSTEM = (
    "You are '미니튜터', a friendly Korean coding-learning tutor embedded in a small chat "
    "popup. Keep answers SHORT and conversational (보통 2~5문장), in KOREAN. Personalize to "
    "the learner using the given context: 현재 활동, 코딩 상태(내부 참고), 최근 오답 기록. "
    "You may reference their recent mistakes to give targeted guidance. Never dump a full "
    "paste-ready solution; nudge their thinking, explain concepts, and suggest next steps. "
    "If the context is empty or the question is general, just answer helpfully. Do NOT reveal "
    "the raw coding-state text to the user."
)


def _tutor_context_block(
    activity: str,
    coding_state: str,
    recent_notes: list,
    evidence: list[Evidence],
    window_days: int,
) -> str:
    parts: list[str] = []
    if activity:
        parts.append(f"[현재 활동]\n{activity}")
    if coding_state:
        parts.append(coding_state)  # 이미 '사용자 비노출' 라벨 포함
    if recent_notes:
        lines = []
        for note in recent_notes[:8]:
            title = getattr(note, "title", "") or "오답노트"
            pattern = getattr(note, "error_pattern", "") or ""
            days = getattr(note, "days_ago", None)
            summary = getattr(note, "summary", "") or ""
            when = f"{days}일 전" if days is not None else ""
            meta = " · ".join(x for x in (pattern, when) if x)
            lines.append(f"- {title}" + (f" ({meta})" if meta else "") + (f": {summary}" if summary else ""))
        parts.append(f"[최근 {window_days}일 오답 기록]\n" + "\n".join(lines))
    if evidence:
        hits = "\n".join(f"- note {e.note_id} {e.title or ''} (유사도 {e.score})" for e in evidence[:5])
        parts.append(f"[질문과 관련된 과거 기록(RAG)]\n{hits}")
    if not parts:
        return ""
    return (
        "다음은 학습자 개인 맥락이다. 답변을 이 맥락에 맞춰 개인화하되, 원문을 그대로 노출하지 말 것.\n\n"
        + "\n\n".join(parts)
    )


async def tutor_reply(
    question: str,
    history: list,
    coding_state: str = "",
    activity: str = "",
    recent_notes: list | None = None,
    evidence: list[Evidence] | None = None,
    window_days: int = 30,
) -> str:
    """미니튜터: 대화 컨텍스트 + 현재 활동 + 코딩 상태 + 최근 오답(RAG)으로 간단 문답."""
    recent_notes = recent_notes or []
    evidence = evidence or []
    messages = [{"role": "system", "content": _TUTOR_SYSTEM}]
    context = _tutor_context_block(activity, coding_state, recent_notes, evidence, window_days)
    if context:
        messages.append({"role": "system", "content": context})
    for turn in (history or [])[-6:]:  # 최근 6턴만 컨텍스트로
        role = "assistant" if getattr(turn, "role", "user") == "assistant" else "user"
        content = (getattr(turn, "content", "") or "").strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    try:
        resp = await _get_client().chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=500,
        )
    except OpenAIError as exc:
        raise LLMCallError(f"openai_error: {exc}") from exc
    return (resp.choices[0].message.content or "").strip()


