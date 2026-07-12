"""내부 통신 보안 테스트 (verify_internal).

X-Internal-API-Key 불일치 → 401, X-Request-ID 누락 → 400, 정상 → 200.
"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import config
from services.security import verify_internal

app = FastAPI()


@app.post("/protected")
async def protected(ctx=Depends(verify_internal)):
    return {"request_id": ctx["request_id"]}


client = TestClient(app)
VALID_KEY = config.INTERNAL_API_KEY


def test_missing_api_key_returns_401():
    resp = client.post("/protected", headers={"X-Request-ID": "req-1"})
    assert resp.status_code == 401


def test_wrong_api_key_returns_401():
    resp = client.post(
        "/protected",
        headers={"X-Internal-API-Key": "definitely-wrong", "X-Request-ID": "req-1"},
    )
    assert resp.status_code == 401


def test_missing_request_id_returns_400():
    resp = client.post("/protected", headers={"X-Internal-API-Key": VALID_KEY})
    assert resp.status_code == 400


def test_valid_headers_pass():
    resp = client.post(
        "/protected",
        headers={"X-Internal-API-Key": VALID_KEY, "X-Request-ID": "req-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["request_id"] == "req-1"
