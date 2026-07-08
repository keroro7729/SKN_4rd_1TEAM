"""오답노트 리트리빙 v0 vs v1 오프라인 성능평가.

목적: '단일 블롭 1벡터(v0)' 대비 '섹션 멀티 청킹 + mean/max 집계(v1)' 의 검색 정밀도 개선을
      동일 임베더(결정적 토큰-해시 BoW) 위에서 **구조 변화만** 분리 측정한다(ChromaDB 불필요).

합성 벤치마크(라벨 有):
  - 4개 오류 유형 클러스터 × 5개 노트 = 20개 오답노트.
  - **노이즈(문제 원문·제출 코드)** 는 클러스터와 무관하게 유사한 보일러플레이트(실제 코테 문제/입출력
    코드가 유형과 무관하게 비슷한 상황을 재현) → v0 블롭을 지배.
  - **신호(회고·AI 코멘트)** 만 유형별로 구분 → v1 이 청킹으로 분리 매칭.
  - 정답(relevant) = 같은 클러스터의 다른 노트들(각 쿼리당 4개).

파이프라인은 실제 코드 경로를 그대로 반영:
  - v0: index=단일 블롭 1벡터, query = "문제명 + 회고 + 태그" 1벡터, score = cosine.
  - v1: index=섹션 청크들, query = 회고 청크 + topic(카테고리·알고리즘), score = 섹션 mean/max 집계.

실행: (fastapi 컨테이너/venv) `python -m services.rag_eval`
"""
from __future__ import annotations

import math
from statistics import fmean
from typing import Dict, List

from services import chroma

# --------------------------------------------------------------------------- #
# 합성 데이터셋                                                                   #
# --------------------------------------------------------------------------- #
# 노이즈(문제 원문/코드) — 오류 유형(cluster)과 **무관한** 문제 주제 5종.
# 서로 다른 어휘를 가지며, (nid-1)%5 로 배정 → 같은 주제가 여러 클러스터에 걸쳐 등장해
# v0 블롭을 유형과 무관하게 끌어당긴다(실제 코테: 같은 실수도 문제마다 지문/코드가 다름).
NOISE_THEMES = [
    {
        "title": "K번째 수 정렬",
        "problem": ("N개의 수로 이루어진 수열이 주어질 때 이를 오름차순으로 정렬한 뒤 "
                    "K번째 원소를 출력하라. 정렬 안정성과 비교 횟수를 고려하라."),
        "code": ("nums = list(map(int, input().split()))\n"
                 "nums.sort()\n"
                 "print(nums[k-1])\n"),
    },
    {
        "title": "그래프 도달 정점 수",
        "problem": ("정점 V와 간선 E로 이루어진 그래프에서 시작 정점으로부터 도달 가능한 "
                    "정점의 수를 너비 우선 탐색으로 구하라. 인접 리스트를 사용하라."),
        "code": ("from collections import deque\n"
                 "graph = [[] for _ in range(v+1)]\n"
                 "q = deque([start]); visited[start] = True\n"
                 "while q:\n    cur = q.popleft()\n"),
    },
    {
        "title": "문자 빈도수",
        "problem": ("문자열 S가 주어질 때 각 알파벳의 등장 빈도를 세고, 가장 많이 나온 "
                    "문자를 출력하라. 대소문자는 구분하지 않는다."),
        "code": ("from collections import Counter\n"
                 "s = input().strip().lower()\n"
                 "cnt = Counter(s)\n"
                 "print(cnt.most_common(1))\n"),
    },
    {
        "title": "약수의 합",
        "problem": ("자연수 M이 주어질 때 M의 모든 약수의 합을 구하라. 완전수 여부도 함께 "
                    "판별하라. 시간 복잡도를 제곱근 범위로 줄여라."),
        "code": ("m = int(input())\n"
                 "total = 0\n"
                 "for d in range(1, int(m**0.5)+1):\n"
                 "    if m % d == 0: total += d\n"),
    },
    {
        "title": "계단 오르기",
        "problem": ("계단을 오르는 방법의 수를 구하라. 한 번에 1칸 또는 2칸 오를 수 있을 때 "
                    "N번째 계단에 도달하는 경우의 수를 점화식으로 계산하라."),
        "code": ("dp = [0]*(n+1)\n"
                 "dp[1] = 1; dp[2] = 2\n"
                 "for i in range(3, n+1):\n"
                 "    dp[i] = dp[i-1] + dp[i-2]\n"),
    },
]

# 유형별 신호(회고/AI 코멘트). 클러스터 내부는 키워드 공유(패러프레이즈), 클러스터 간은 구분.
CLUSTERS = [
    {
        "name": "배열 인덱스 범위 초과",
        "category": "자료구조", "algo": ["배열"], "difficulty": "beginner",
        "problem_core": "배열의 경계 인덱스를 안전하게 다루는 것이 핵심이다.",
        "solution": "반복 범위를 배열 길이에 맞추고 마지막 인덱스 접근을 점검한다.",
        "ai_feedback": "경계 조건을 표로 먼저 정리하면 인덱스 실수를 줄일 수 있다.",
        "retros": [
            "배열 인덱스 범위를 초과해서 런타임 에러가 났다",
            "리스트 끝에서 i+1 인덱스에 접근하다 인덱스 오류가 발생했다",
            "반복문에서 인덱스가 배열 범위를 벗어나 out of range 예외가 떴다",
            "경계 인덱스 처리를 안 해서 배열 범위 밖을 참조했다",
            "인덱스 상한을 잘못 잡아 마지막 원소 다음 칸을 읽었다",
        ],
        "causes": [
            "range 상한을 n으로 두고 a[i+1]을 참조해 인덱스가 범위를 벗어났다",
            "마지막 인덱스에서 다음 원소에 접근해 배열 범위를 초과했다",
            "경계 인덱스 검사를 빼먹어 리스트 범위 밖을 읽었다",
            "인덱스 상한 조건이 틀려 배열 끝을 넘어 접근했다",
            "반복 인덱스가 배열 길이와 어긋나 범위 초과가 났다",
        ],
        "improvements": [
            "반복 상한을 n-1로 바꾸거나 i+1 접근 전에 인덱스 범위를 확인하라",
            "a[i+1] 접근 조건을 i < n-1 로 제한해 인덱스 초과를 막아라",
            "경계 인덱스에서 범위 검사를 추가해 배열 밖 참조를 방지하라",
            "인덱스 상한을 배열 길이에 맞춰 마지막 칸 다음을 읽지 않게 하라",
            "루프 범위를 배열 크기에 정렬하고 경계 인덱스를 따로 처리하라",
        ],
    },
    {
        "name": "정수 자료형 오버플로우",
        "category": "알고리즘", "algo": ["수학"], "difficulty": "intermediate",
        "problem_core": "큰 수 누적 시 자료형 범위와 오버플로우를 고려하는 것이 핵심이다.",
        "solution": "누적 합의 최대 크기를 추정하고 더 넓은 자료형이나 모듈러를 사용한다.",
        "ai_feedback": "입력 상한으로 최댓값을 미리 계산해 오버플로우 가능성을 점검하라.",
        "retros": [
            "정수 오버플로우가 나서 합이 음수로 뒤집혔다",
            "자료형 범위를 넘겨 int 오버플로우로 값이 깨졌다",
            "큰 수 누적에서 오버플로우가 발생해 결과가 틀렸다",
            "곱셈 누적이 자료형 최대값을 초과해 오버플로우가 났다",
            "합이 int 범위를 벗어나 오버플로우로 잘못된 값이 나왔다",
        ],
        "causes": [
            "누적 합이 32비트 정수 범위를 초과해 오버플로우가 발생했다",
            "곱셈 결과가 자료형 최대값을 넘어 값이 뒤집혔다",
            "큰 입력에서 합계가 int 범위를 초과해 오버플로우가 났다",
            "자료형을 int로 두어 누적 중 오버플로우가 생겼다",
            "최댓값 추정을 안 해 오버플로우 경계를 넘겼다",
        ],
        "improvements": [
            "누적 변수를 더 넓은 자료형으로 바꾸거나 모듈러 연산을 적용하라",
            "합의 최대 크기를 계산해 오버플로우가 없는 자료형을 선택하라",
            "곱셈 전에 범위를 점검하고 필요 시 모듈러로 오버플로우를 피하라",
            "입력 상한으로 최댓값을 추정해 자료형 범위를 확보하라",
            "오버플로우 가능 지점을 넓은 자료형으로 승격하라",
        ],
    },
    {
        "name": "재귀 종료 조건 누락",
        "category": "알고리즘", "algo": ["완전탐색"], "difficulty": "intermediate",
        "problem_core": "재귀의 종료 조건(base case)을 정확히 세우는 것이 핵심이다.",
        "solution": "종료 조건을 먼저 정의하고 재귀가 그 조건으로 수렴하는지 확인한다.",
        "ai_feedback": "재귀 호출 전에 종료 조건과 감소하는 인자를 표로 확인하라.",
        "retros": [
            "재귀 종료 조건을 빠뜨려 무한 재귀로 스택 오버플로우가 났다",
            "base case를 안 만들어 재귀가 끝나지 않고 스택이 넘쳤다",
            "재귀 탈출 조건이 없어 함수가 무한히 호출됐다",
            "종료 조건 범위가 틀려 재귀가 수렴하지 않았다",
            "재귀 기저 조건을 잘못 잡아 무한 재귀에 빠졌다",
        ],
        "causes": [
            "종료 조건이 없어 재귀 호출이 무한히 반복됐다",
            "base case 범위가 틀려 재귀가 멈추지 않았다",
            "탈출 조건을 빠뜨려 스택 오버플로우가 발생했다",
            "재귀 인자가 감소하지 않아 종료 조건에 도달하지 못했다",
            "기저 조건 판정이 어긋나 무한 재귀가 됐다",
        ],
        "improvements": [
            "가장 작은 입력에 대한 종료 조건을 먼저 정의하고 반환하라",
            "base case를 추가하고 재귀 인자가 매번 감소하는지 확인하라",
            "탈출 조건 범위를 바로잡아 재귀가 수렴하게 만들어라",
            "종료 조건을 표로 검증한 뒤 재귀 호출을 배치하라",
            "기저 조건 판정을 고쳐 무한 재귀를 제거하라",
        ],
    },
    {
        "name": "부동소수점 비교 오차",
        "category": "알고리즘", "algo": ["수학"], "difficulty": "advanced",
        "problem_core": "부동소수점의 오차를 감안한 비교(epsilon)를 쓰는 것이 핵심이다.",
        "solution": "실수 동등 비교 대신 허용 오차 이내인지로 판정한다.",
        "ai_feedback": "실수는 == 대신 abs(a-b) < eps 로 비교하는 습관을 들여라.",
        "retros": [
            "부동소수점 비교를 == 로 해서 오차 때문에 틀렸다",
            "실수 동등 비교에서 부동소수점 오차로 판정이 어긋났다",
            "float 비교를 정확히 같은지로 해서 미세 오차에 걸렸다",
            "부동소수점 반올림 오차를 무시해 비교 결과가 틀렸다",
            "실수 비교에 허용 오차를 안 써서 오차로 답이 달라졌다",
        ],
        "causes": [
            "실수를 == 로 비교해 부동소수점 오차로 판정이 틀렸다",
            "허용 오차 없이 float 동등 비교를 해 미세 오차에 걸렸다",
            "반올림 오차를 고려하지 않아 비교가 어긋났다",
            "부동소수점 표현 한계를 무시한 정확 비교로 실패했다",
            "eps 없이 실수 비교를 해 오차로 결과가 달라졌다",
        ],
        "improvements": [
            "동등 비교를 abs(a-b) < eps 형태의 허용 오차 비교로 바꿔라",
            "float == 대신 작은 epsilon 이내인지로 판정하라",
            "반올림 오차를 감안해 허용 오차 기반 비교를 적용하라",
            "부동소수점 비교에 eps 를 도입해 오차 영향을 없애라",
            "정확 비교 대신 오차 허용 범위 비교로 안정화하라",
        ],
    },
]


def build_notes() -> List[dict]:
    """클러스터 정의를 20개 노트로 전개."""
    notes: List[dict] = []
    nid = 1
    for cluster_idx, c in enumerate(CLUSTERS):
        for k in range(len(c["retros"])):
            theme = NOISE_THEMES[(nid - 1) % len(NOISE_THEMES)]  # 유형과 무관한 문제 주제
            notes.append({
                "id": nid,
                "cluster": cluster_idx,
                "title": f"{theme['title']} #{nid}",  # 제목=문제명(노이즈), 실수 유형과 무관
                "difficulty": c["difficulty"],
                "category": c["category"],
                "algo": c["algo"],
                "problem_statement": theme["problem"],
                "code": theme["code"],
                "retro": c["retros"][k],
                "problem_core": c["problem_core"],
                "solution": c["solution"],
                "cause": c["causes"][k],
                "improvement": c["improvements"][k],
                "ai_feedback": c["ai_feedback"],
            })
            nid += 1
    return notes


# --------------------------------------------------------------------------- #
# v0 / v1 인덱싱·쿼리 구성 (실제 코드 경로 반영)                                     #
# --------------------------------------------------------------------------- #
def v0_blob(note: dict) -> str:
    """v0: 문제명·난이도·태그·회고·결과·에러·코드·분석을 뭉친 단일 문서."""
    return "\n".join([
        f"문제명: {note['title']}",
        f"난이도: {note['difficulty']}",
        f"태그: {', '.join(note['algo'])}",
        f"사용자 코멘트: {note['retro']}",
        "제출 결과: wrong",
        "오류 메시지: ",
        f"제출 코드: {note['code']}",
        f"문제 핵심: {note['problem_core']}",
        f"풀이 과정: {note['solution']}",
        f"오답 원인: {note['cause']}",
        f"개선 사항: {note['improvement']}",
    ])


def v0_query(note: dict) -> str:
    """v0 검색 쿼리: 문제명 + 회고 + 태그 (구 라우터 그대로)."""
    return f"{note['title']} {note['retro']} {' '.join(note['algo'])}"


def v1_sections(note: dict) -> Dict[str, str]:
    """v1 인덱스 섹션: 회고 + AI 코멘트만(문제 원문/코드/난이도/에러 제외)."""
    return {
        "retrospection": note["retro"],
        "problem_core": note["problem_core"],
        "solution": note["solution"],
        "cause": note["cause"],
        "improvement": note["improvement"],
        "ai_feedback": note["ai_feedback"],
    }


def v1_query_chunks(note: dict) -> List[str]:
    """v1 검색 쿼리 청크: 회고 청크 + topic(카테고리·알고리즘). (분석 전 상태 재현)"""
    chunks = list(chroma.chunk_text(note["retro"]))
    topic = chroma.build_topic_text(note["category"], note["algo"])
    if topic:
        chunks.append(topic)
    return chunks


# --------------------------------------------------------------------------- #
# 스코어러                                                                       #
# --------------------------------------------------------------------------- #
def v0_scores(query_note: dict, candidates: List[dict]) -> List[tuple]:
    qvec = chroma.embed_text(v0_query(query_note))
    out = []
    for cand in candidates:
        cvec = chroma.embed_text(v0_blob(cand))
        out.append((cand["id"], cand["cluster"], chroma.cosine(qvec, cvec)))
    return sorted(out, key=lambda x: x[2], reverse=True)


def v1_scores(query_note: dict, candidates: List[dict]) -> List[tuple]:
    q_vecs = [chroma.embed_text(qc) for qc in v1_query_chunks(query_note)]
    out = []
    for cand in candidates:
        section_sims: Dict[str, float] = {}
        for section, ctext in chroma.build_note_chunks(v1_sections(cand), cand["category"], cand["algo"]):
            cvec = chroma.embed_text(ctext)
            best = max((chroma.cosine(qv, cvec) for qv in q_vecs), default=0.0)
            if best > section_sims.get(section, 0.0):
                section_sims[section] = best
        out.append((cand["id"], cand["cluster"], chroma.aggregate_section_sims(section_sims)))
    return sorted(out, key=lambda x: x[2], reverse=True)


# --------------------------------------------------------------------------- #
# 지표                                                                          #
# --------------------------------------------------------------------------- #
def _metrics(ranked: List[tuple], query_cluster: int, k: int) -> Dict[str, float]:
    rels = [1 if cluster == query_cluster else 0 for (_id, cluster, _s) in ranked]
    total_rel = sum(rels)
    topk = rels[:k]
    precision = sum(topk) / k
    recall = sum(topk) / total_rel if total_rel else 0.0
    # MRR
    mrr = 0.0
    for i, r in enumerate(rels, start=1):
        if r:
            mrr = 1.0 / i
            break
    # nDCG@k
    dcg = sum(r / math.log2(i + 1) for i, r in enumerate(topk, start=1))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, total_rel) + 1))
    ndcg = dcg / idcg if idcg else 0.0
    return {"precision": precision, "recall": recall, "mrr": mrr, "ndcg": ndcg}


def evaluate(k: int = 4) -> Dict[str, Dict[str, float]]:
    notes = build_notes()
    agg = {"v0": [], "v1": []}
    for q in notes:
        candidates = [n for n in notes if n["id"] != q["id"]]
        agg["v0"].append(_metrics(v0_scores(q, candidates), q["cluster"], k))
        agg["v1"].append(_metrics(v1_scores(q, candidates), q["cluster"], k))
    summary = {}
    for version, rows in agg.items():
        summary[version] = {m: round(fmean(r[m] for r in rows), 4) for m in rows[0]}
    return summary


def main() -> None:
    k = 4
    notes = build_notes()
    summary = evaluate(k)
    print(f"# RAG 리트리빙 성능평가  (노트 {len(notes)}개 · 클러스터 {len(CLUSTERS)}개 · k={k})")
    print(f"{'metric':<12}{'v0(단일블롭)':>16}{'v1(섹션청킹)':>16}{'개선율':>12}")
    for m in ("precision", "recall", "mrr", "ndcg"):
        v0, v1 = summary["v0"][m], summary["v1"][m]
        delta = f"{((v1 - v0) / v0 * 100):+.1f}%" if v0 else "n/a"
        print(f"{m:<12}{v0:>16.4f}{v1:>16.4f}{delta:>12}")
    # 정성 예시: 1번 노트 쿼리의 top-5
    q = notes[0]
    cands = [n for n in notes if n["id"] != q["id"]]
    print(f"\n[예시] 쿼리 노트 #{q['id']} (클러스터 '{CLUSTERS[q['cluster']]['name']}') 상위 5")
    for tag, ranked in (("v0", v0_scores(q, cands)), ("v1", v1_scores(q, cands))):
        top = ", ".join(f"#{i}({'O' if cl == q['cluster'] else 'X'},{s:.2f})" for i, cl, s in ranked[:5])
        print(f"  {tag}: {top}")


if __name__ == "__main__":
    main()
