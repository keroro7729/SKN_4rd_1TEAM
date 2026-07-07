"""테스트케이스 생성 에이전트 - 실제 OpenAI 연동.

정답(레퍼런스) 코드 + 랜덤 입력 생성기 + 엣지/시간 케이스 입력을 LLM 으로 생성한다.
실제 실행/검증은 Django 오케스트레이터가 Worker(code_eval)에 위임한다.
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI, OpenAIError

import config

log = logging.getLogger("ai_research")


class AuthoringError(RuntimeError):
    """생성 실패(키 미설정/LLM 오류/JSON 파싱 실패)."""


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise AuthoringError("OPENAI_API_KEY 가 설정되지 않았습니다.")
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


_GEN_SYSTEM = (
    "You are an expert competitive-programming test-case author. "
    "Given a problem statement (often in Korean), you produce: a correct reference "
    "solution, a random small-input generator, and explicit edge/timing inputs. "
    "You reply ONLY with a single JSON object. All programs are self-contained "
    "Python 3, read ALL input from stdin, and print ONLY the answer to stdout."
)


def _gen_user_prompt(problem: dict) -> str:
    return f"""Problem title: {problem.get('title', '')}

Problem statement:
{problem.get('description', '')}

Constraints:
{problem.get('constraints', '') or '(not explicitly given — infer reasonable small bounds)'}

Return a JSON object with EXACTLY these keys:
- "solution_code": string. A CORRECT Python 3 reference solution. Reads all input from
  stdin, prints only the final answer to stdout. Deterministic. No prompts, no debug prints.
- "generator_code": string. A Python 3 program that reads a single integer `seed` from the
  FIRST line of stdin, does `random.seed(seed)`, and prints ONE random VALID test input to
  stdout in EXACTLY the input format the solution expects. Pick the random ranges WIDE enough
  that different seeds almost never produce identical inputs: draw numeric values from a broad
  range (e.g. up to 1_000_000, or the problem's stated maximum) and also randomize the sizes
  (e.g. array length chosen randomly up to a few hundred), while staying within the problem
  constraints and keeping each run fast (well under ~2 seconds). Do NOT use tiny ranges such as
  values only 1..20 or fixed sizes — those cause frequent duplicate test cases.
- "edge_inputs": array of 1..5 strings. Each string is a COMPLETE stdin for a tricky small
  edge case (minimum sizes, boundaries, ties, duplicates, negatives, empty-ish), matching the
  exact input format.
- "time_inputs": array of 1..5 strings. Each is a COMPLETE stdin for a LARGER case (near the
  upper constraint) used only to measure running time.
- "notes": short string describing the assumed input/output format.

The solution_code and generator_code MUST agree on the input format. Output valid JSON only."""


async def _chat_json(system: str, user: str) -> dict:
    try:
        resp = await _get_client().chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise AuthoringError(f"OpenAI 호출 실패: {exc}") from exc
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AuthoringError(f"LLM JSON 파싱 실패: {exc}") from exc
    if not isinstance(data, dict):
        raise AuthoringError("LLM 응답이 JSON 객체가 아닙니다.")
    return data


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value][:5]


async def generate(problem: dict) -> dict:
    """정답 코드 + 제너레이터 + 엣지/시간 입력 생성."""
    data = await _chat_json(_GEN_SYSTEM, _gen_user_prompt(problem))
    solution = str(data.get("solution_code") or "").strip()
    generator = str(data.get("generator_code") or "").strip()
    if not solution or not generator:
        raise AuthoringError("solution_code/generator_code 가 비어 있습니다.")
    return {
        "solution_code": solution,
        "generator_code": generator,
        "edge_inputs": _as_str_list(data.get("edge_inputs")),
        "time_inputs": _as_str_list(data.get("time_inputs")),
        "notes": str(data.get("notes") or ""),
    }


_FIX_SYSTEM = (
    "You are debugging a Python 3 reference solution for a programming problem. "
    "You reply ONLY with a JSON object. The fixed program reads all input from stdin "
    "and prints only the answer to stdout."
)


async def fix(problem: dict, solution_code: str, error: str, sample_input: str = "") -> dict:
    """실행 오류/불일치를 바탕으로 정답 코드를 수정한다 (디버깅 루프)."""
    user = f"""Problem title: {problem.get('title', '')}

Problem statement:
{problem.get('description', '')}

Current solution (produced wrong result or crashed):
```python
{solution_code}
```

Failing sample stdin:
{sample_input or '(n/a)'}

Observed error / mismatch:
{error}

Return a JSON object with keys:
- "solution_code": the FIXED full Python 3 program (stdin -> stdout).
- "notes": one short line on what was fixed.
Output valid JSON only."""
    data = await _chat_json(_FIX_SYSTEM, user)
    fixed = str(data.get("solution_code") or "").strip()
    if not fixed:
        raise AuthoringError("수정된 solution_code 가 비어 있습니다.")
    return {"solution_code": fixed, "notes": str(data.get("notes") or "")}
