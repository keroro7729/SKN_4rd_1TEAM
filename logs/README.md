# logs/ — 통합 로그 디렉토리

모든 컴포넌트의 **개발/디버깅/AI연구용** 로그가 이 디렉토리에 모인다.
docker-compose 에서 `./logs` 를 각 컨테이너의 `/app/logs` 로 bind mount 하므로
**컨테이너를 지워도 로그는 호스트에 남는다**(named volume 아님, 직접 열람 가능).

로컬 실행 시에도 각 컴포넌트가 `<repo루트>/logs` 를 자동 사용한다(환경변수 `LOG_DIR` 로 재정의 가능).

## 레이아웃

```
logs/
├─ django/app.log       # Django 웹: 요청/에러/서비스 로그 (회전 5MB×5)
├─ fastapi/app.log      # FastAPI: 일반 애플리케이션 로그
├─ worker/app.log       # Worker: jobs polling/실행 로그
└─ ai/research.jsonl    # ★ AI 연구용: LLM/RAG 이벤트를 JSON Lines 로 축적
```

## ai/research.jsonl (AI 연구/분석용)

힌트·오답분석·RAG 검색 등 AI 이벤트를 **한 줄 = 한 JSON** 으로 남긴다.
나중에 프롬프트 튜닝·RAG 품질 분석·모델 비교에 그대로 활용할 수 있게 구조화한다.

예시:
```json
{"ts":"2026-07-03T05:00:00+00:00","event":"hint","problem_id":12,"hint_level":2,"model":"gpt-4o-mini"}
{"ts":"2026-07-03T05:00:04+00:00","event":"rag_search","user_id":7,"top_k":5,"hits":3}
```

분석 예: `jq -c 'select(.event=="hint")' logs/ai/research.jsonl`

## 설정 (환경변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | 루트 로그 레벨 (DEBUG/INFO/WARNING/ERROR) |
| `LOG_DIR` | (비움) | 비우면 `<repo루트>/logs`. Docker compose 는 `/app/logs` 주입 |

> 자세한 설계는 `llm_wiki/5. WOOKS_CODING_로깅_시스템_v0.1.md` 참고.
