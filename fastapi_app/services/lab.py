"""AI 실험 랩 - 에이전트 그래프 정의 + 단일 노드 실행(프롬프트 주입).

핵심 로직은 여기(FastAPI)에 있고, Django 실험실은 그래프 조회 + 프롬프트 주입/실행/비교만 한다.
LLM 노드의 system 프롬프트는 각 서비스에서 그대로 임포트해 정합성을 유지하고,
user 프롬프트는 실험용 템플릿을 두어 프롬프트 주입 시 시작점으로 쓴다.
"""
from __future__ import annotations

import json
import time

from openai import AsyncOpenAI, OpenAIError

import config
from services.authoring import _FIX_SYSTEM, _GEN_SYSTEM
from services.coding_state import _SYSTEM as CS_SYSTEM
from services.llm import _ANALYZE_SYSTEM, _HINT_SYSTEM
from services.wrong_note_report import _SYSTEM as WNR_SYSTEM


class LabError(RuntimeError):
    pass


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise LabError("OPENAI_API_KEY 가 설정되지 않았습니다.")
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


class _Safe(dict):
    def __missing__(self, key):
        return ""


# --- 에이전트 그래프(노드/에지) ---
AGENTS = [
    {"id": "hint", "label": "힌트 에이전트",
     "nodes": ["hint.generate"], "edges": []},
    {"id": "wrong_note_analyze", "label": "오답 분석",
     "nodes": ["wna.analyze"], "edges": []},
    {"id": "coding_state", "label": "코딩상태 요약",
     "nodes": ["cs.summarize"], "edges": []},
    {"id": "wrong_note_report", "label": "오답노트 리포트(2단계 RAG)",
     "nodes": ["wnr.retrieve1", "wnr.report", "wnr.retrieve2"],
     "edges": [["wnr.retrieve1", "wnr.report"], ["wnr.report", "wnr.retrieve2"]]},
    {"id": "testcase_gen", "label": "테스트케이스 생성",
     "nodes": ["tc.generate", "tc.eval_generator", "tc.eval_solution", "tc.fix"],
     "edges": [["tc.generate", "tc.eval_generator"], ["tc.eval_generator", "tc.eval_solution"],
               ["tc.eval_solution", "tc.fix"], ["tc.fix", "tc.eval_solution"]]},
]


# --- 노드 정의 (LLM 노드는 runnable) ---
NODES = {
    "hint.generate": {
        "agent": "hint", "label": "힌트 생성", "kind": "llm", "output": "json", "runnable": True,
        "system": _HINT_SYSTEM,
        "user_template": (
            "문제: {title} (난이도 {difficulty})\n{description}\n제약조건: {constraints}\n\n"
            "학습자가 지금 작성한 코드:\n```\n{user_code}\n```\n"
            "힌트 단계(hint_level): {hint_level} / 3\n학습자 추정 수준: {level}\n{coding_state}\n\n"
            "위 수준·현재 코드 상태를 고려해 hint_level {hint_level} 힌트를 만들어라. "
            "정답·전체 접근·코드 금지. JSON {{\"content\": string}} 로만 답하라."
        ),
        "sample": {"title": "두 수의 합(인덱스)", "difficulty": "초급",
                   "description": "정수 배열 nums 와 target 이 주어질 때 합이 target 인 두 인덱스를 출력.",
                   "constraints": "2 <= len(nums) <= 10000", "user_code": "for i in range(len(nums)):\n    # 여기서 뭘 하지?",
                   "hint_level": 1, "level": "입문", "coding_state": ""},
    },
    "wna.analyze": {
        "agent": "wrong_note_analyze", "label": "오답 분석", "kind": "llm", "output": "json", "runnable": True,
        "system": _ANALYZE_SYSTEM,
        "user_template": (
            "제출 코드:\n```\n{code}\n```\n사용자 회고:\n{comment}\n{coding_state}\n\n"
            "아래 키를 가진 JSON 으로만 답하라(한국어, 정답 미노출): "
            "problem_core, cause, solution, caution."
        ),
        "sample": {"code": "a,b=map(int,input().split())\nprint(a+b)", "comment": "여러 줄 입력을 한 줄로 가정해 런타임 에러가 났다.", "coding_state": ""},
    },
    "cs.summarize": {
        "agent": "coding_state", "label": "코딩상태 요약", "kind": "llm", "output": "json", "runnable": True,
        "system": CS_SYSTEM,
        "user_template": (
            "학습자 집계 통계(JSON):\n{stats}\n\n"
            "아래 키를 가진 JSON 으로만 답하라(한국어): "
            "summary, level, strengths[], weaknesses[], recurring_mistakes[], recommended_focus[]."
        ),
        "sample": {"stats": '{"total_submissions": 5, "accuracy": 0.6, "solved_tags": ["Array"], "failed_tags": ["DP"], "recurring_error_patterns": [{"pattern": "DP 초기값 오류", "count": 2}]}'},
    },
    "tc.generate": {
        "agent": "testcase_gen", "label": "정답코드/생성기 생성", "kind": "llm", "output": "json", "runnable": True,
        "system": _GEN_SYSTEM,
        "user_template": (
            "Problem title: {title}\n\nProblem statement:\n{description}\n\nConstraints:\n{constraints}\n\n"
            "Return JSON with keys: solution_code, generator_code, edge_inputs[], time_inputs[], notes. "
            "generator reads an int seed from stdin and prints ONE random VALID input with WIDE ranges "
            "(few duplicates). JSON only."
        ),
        "sample": {"title": "두 수의 합", "description": "첫 줄에 두 정수 a b. a+b 출력.", "constraints": "1<=a,b<=1000000"},
    },
    "tc.fix": {
        "agent": "testcase_gen", "label": "정답코드 수정(디버깅)", "kind": "llm", "output": "json", "runnable": True,
        "system": _FIX_SYSTEM,
        "user_template": (
            "Problem title: {title}\n\nProblem statement:\n{description}\n\n"
            "Current solution:\n```python\n{solution_code}\n```\n\nFailing stdin:\n{sample_input}\n\n"
            "Observed error:\n{error}\n\nReturn JSON {{\"solution_code\": ..., \"notes\": ...}}."
        ),
        "sample": {"title": "두 수의 합", "description": "a+b 출력", "solution_code": "print(input()+input())", "sample_input": "1 2", "error": "TypeError"},
    },
    "wnr.report": {
        "agent": "wrong_note_report", "label": "오답 리포트 생성", "kind": "llm", "output": "json", "runnable": True,
        "system": WNR_SYSTEM,
        "user_template": (
            "문제: {problem_title} (난이도 {difficulty})\n태그: {tags}\n제출 결과: {result}\n"
            "제출 코드:\n```\n{submitted_code}\n```\n사용자 회고:\n{user_comment}\n"
            "과거 유사 오답노트(참고): {similar}\n\n"
            "JSON 으로만 답하라(한국어): retrospection_feedback, missed_points[], learning_direction[], summary."
        ),
        "sample": {"problem_title": "이분탐색 최소 파라미터", "difficulty": "중급", "tags": "binary_search", "result": "wrong", "submitted_code": "lo,hi=0,n\nwhile lo<hi:\n mid=(lo+hi)//2", "user_comment": "경계 처리에서 무한루프가 났다.", "similar": "(없음)"},
    },
    # --- 비-LLM 노드(그래프 보기 전용) ---
    "wnr.retrieve1": {"agent": "wrong_note_report", "label": "1차 리트리빙(회고)", "kind": "retrieval", "runnable": False},
    "wnr.retrieve2": {"agent": "wrong_note_report", "label": "최종 리트리빙", "kind": "retrieval", "runnable": False},
    "tc.eval_generator": {"agent": "testcase_gen", "label": "생성기 실행(Worker)", "kind": "worker", "runnable": False},
    "tc.eval_solution": {"agent": "testcase_gen", "label": "정답코드 실행(Worker)", "kind": "worker", "runnable": False},
}


def _render_user(node: dict, inputs: dict) -> str:
    merged = {**(node.get("sample") or {}), **(inputs or {})}
    return node["user_template"].format_map(_Safe(merged))


def get_graph() -> dict:
    nodes = {}
    for nid, n in NODES.items():
        meta = {
            "id": nid, "agent": n["agent"], "label": n["label"],
            "kind": n["kind"], "runnable": n.get("runnable", False),
            "output": n.get("output", ""),
        }
        if n.get("runnable"):
            meta["default_system"] = n["system"]
            meta["default_user"] = _render_user(n, {})
            meta["sample"] = n.get("sample", {})
        nodes[nid] = meta
    return {"agents": AGENTS, "nodes": nodes}


async def run_node(node_id: str, inputs: dict, system: str = "", user: str = "", model: str = "") -> dict:
    node = NODES.get(node_id)
    if node is None:
        raise LabError(f"unknown node: {node_id}")
    if not node.get("runnable"):
        raise LabError(f"node '{node_id}' 는 LLM 노드가 아니라 랩에서 실행할 수 없습니다({node['kind']}).")

    system_used = system or node["system"]
    user_used = user or _render_user(node, inputs)
    model_used = model or config.OPENAI_MODEL
    kwargs = {}
    if node.get("output") == "json":
        kwargs["response_format"] = {"type": "json_object"}

    started = time.monotonic()
    try:
        resp = await _get_client().chat.completions.create(
            model=model_used,
            messages=[
                {"role": "system", "content": system_used},
                {"role": "user", "content": user_used},
            ],
            temperature=0.3,
            **kwargs,
        )
    except OpenAIError as exc:
        raise LabError(f"openai_error: {exc}") from exc
    content = resp.choices[0].message.content or ""
    pretty = content
    if node.get("output") == "json":
        try:
            pretty = json.dumps(json.loads(content), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    return {
        "node_id": node_id,
        "output": pretty,
        "system_used": system_used,
        "user_used": user_used,
        "model": model_used,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
