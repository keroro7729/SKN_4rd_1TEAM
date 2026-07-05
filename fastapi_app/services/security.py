"""내부 통신 보안 (지시문 규칙 9): X-Internal-API-Key / X-Request-ID."""
from typing import Optional

from fastapi import Header, HTTPException, status

import config


async def verify_internal(
    x_internal_api_key: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None),
) -> dict:
    """Django 내부 호출만 허용하고 요청 추적 ID를 강제한다."""
    if x_internal_api_key != config.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal api key",
        )
    if not x_request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing X-Request-ID",
        )
    return {"request_id": x_request_id}
