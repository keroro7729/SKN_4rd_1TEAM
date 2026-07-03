"""내부 통신 보안 (지시문 규칙 9): X-Internal-API-Key / X-Request-ID."""
from typing import Optional

from fastapi import Header, HTTPException, status

import config


async def verify_internal(
    x_internal_api_key: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None),
) -> dict:
    """Django 내부 호출만 허용. API Key 불일치 시 401."""
    if x_internal_api_key != config.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal api key",
        )
    return {"request_id": x_request_id}
