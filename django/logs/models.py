"""운영 로그 모델 (지시문 §7, F-13/F-15): LLMRequestLog · ErrorLog.

- LLMRequestLog: FastAPI AI 호출 요청/응답 추적. status 는 LLM_STATUS_CHOICES(=common.LLMStatus 동기화).
  request_id(X-Request-ID) 는 unique — Django↔FastAPI 상관관계 추적 키.
- ErrorLog: 컴포넌트별(source) 예외 수집(§13). 파일 로그(logs/)와 별개로 DB 조회용.
"""
from django.conf import settings
from django.db import models

from config.choices import (
    ERROR_SOURCE_CHOICES,
    LLM_REQUEST_TYPE_CHOICES,
    LLM_STATUS_CHOICES,
)


class LLMRequestLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_logs",
        verbose_name="회원",
    )
    request_type = models.CharField(
        "요청유형", max_length=30, choices=LLM_REQUEST_TYPE_CHOICES
    )
    request_id = models.CharField("요청ID", max_length=64, unique=True)
    input_text = models.TextField("입력", blank=True)
    response_text = models.TextField("응답", blank=True)
    status = models.CharField(
        "상태", max_length=20, choices=LLM_STATUS_CHOICES, default="pending"
    )
    error_type = models.CharField("오류유형", max_length=100, blank=True)
    error_message = models.TextField("오류메시지", blank=True)
    created_at = models.DateTimeField("생성일", auto_now_add=True)
    completed_at = models.DateTimeField("완료시각", null=True, blank=True)

    class Meta:
        verbose_name = "LLM 요청 로그"
        verbose_name_plural = "LLM 요청 로그"
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.request_type} · {self.request_id} · {self.status}"


class ErrorLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_logs",
        verbose_name="회원",
    )
    source = models.CharField("발생원", max_length=20, choices=ERROR_SOURCE_CHOICES)
    level = models.CharField("레벨", max_length=20, default="error")
    path = models.CharField("경로", max_length=255, blank=True)
    error_type = models.CharField("오류유형", max_length=100, blank=True)
    message = models.TextField("메시지", blank=True)
    traceback = models.TextField("트레이스백", blank=True)
    is_resolved = models.BooleanField("해결됨", default=False)
    created_at = models.DateTimeField("발생일", auto_now_add=True)

    class Meta:
        verbose_name = "에러 로그"
        verbose_name_plural = "에러 로그"
        indexes = [models.Index(fields=["source", "level", "created_at"])]

    def __str__(self):
        return f"[{self.source}] {self.error_type or self.level}"
