"""LangGraph 에이전트 정의 (스캐폴딩 스텁).

힌트 / 오답분석 / 내 노트 질의응답 흐름을 그래프로 제어한다.
실제 그래프 구성은 STEP-06.

계획:
- hint_agent:     input -> (level별 프롬프트) -> OpenAI -> HintResponse
- analyze_agent:  input -> RAG(chroma) -> 분석 프롬프트 -> OpenAI -> 4개 섹션
- ask_agent:      question -> RAG(chroma, user_id 필터) -> 근거 기반 답변
"""

# TODO(STEP-06): from langgraph.graph import StateGraph 등으로 그래프 빌드
def build_hint_agent():
    raise NotImplementedError("STEP-06에서 구현")


def build_analyze_agent():
    raise NotImplementedError("STEP-06에서 구현")


def build_ask_agent():
    raise NotImplementedError("STEP-06에서 구현")
