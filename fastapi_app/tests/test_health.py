"""헬스체크 엔드포인트 테스트 (/ai/health).

health 라우터는 config 만 의존하므로 chromadb/openai 없이 검증 가능.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import health

app = FastAPI()
app.include_router(health.router)
client = TestClient(app)


def test_health_returns_ok_without_auth():
    resp = client.get("/ai/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # 실제 구현 상태 문자열(옛 not_implemented 하드코딩 정리 확인)
    assert body["llm_status"] in ("operational", "no_api_key")
    assert body["embed_backend"] in ("openai", "hash")
    assert "model" in body and "collection" in body
