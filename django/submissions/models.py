"""제출/실행 모델 (지시문 §7): Submission · ExecutionJob.

제출이력(Submission)과 실행작업(ExecutionJob)은 별도 모델이다.
  - Submission.result : 사용자에게 보일 최종 채점 결과 (도메인 기록, 영구)
  - ExecutionJob.status: Worker 처리 생명주기 (운영/재시도)
  - 1 Submission ─ N ExecutionJob (Job 이 submission FK 보유)
설계 근거: llm_wiki/6. WOOKS_CODING_데이터모델_문제_제출_Job_오답노트_v0.1.md §5
"""
from django.conf import settings
from django.db import models

from config.choices import (
    JOB_STATUS_CHOICES,
    JOB_TYPE_CHOICES,
    SUBMISSION_RESULT_CHOICES,
    SUBMISSION_TYPE_CHOICES,
)
from problems.models import Problem


class Submission(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="회원",
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="문제",
    )
    code = models.TextField("제출코드")
    result = models.CharField(
        "채점결과", max_length=20, choices=SUBMISSION_RESULT_CHOICES, default="pending"
    )
    submission_type = models.CharField(
        "제출유형",
        max_length=20,
        choices=SUBMISSION_TYPE_CHOICES,
        default="submit",
        db_index=True,
    )
    output = models.TextField("실행출력", blank=True)
    error_message = models.TextField("오류메시지", blank=True)
    elapsed_ms = models.PositiveIntegerField("실행시간(ms)", null=True, blank=True)
    created_at = models.DateTimeField("제출일", auto_now_add=True)

    class Meta:
        verbose_name = "제출"
        verbose_name_plural = "제출"
        indexes = [
            models.Index(fields=["user", "problem", "created_at"]),
            models.Index(fields=["user", "submission_type", "created_at"]),
        ]

    def __str__(self):
        return f"Submission#{self.pk} · u{self.user_id} p{self.problem_id} · {self.result}"


class ExecutionJob(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name="회원",
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name="제출",
    )
    job_type = models.CharField(
        "작업유형", max_length=20, choices=JOB_TYPE_CHOICES, default="code_run"
    )
    status = models.CharField(
        "처리상태", max_length=20, choices=JOB_STATUS_CHOICES, default="pending"
    )
    input_payload = models.JSONField("입력페이로드", default=dict, blank=True)
    result_payload = models.JSONField("결과페이로드", default=dict, blank=True)
    retry_count = models.PositiveIntegerField("재시도횟수", default=0)
    max_retry = models.PositiveIntegerField("최대재시도", default=1)
    worker_id = models.CharField("워커ID", max_length=64, blank=True)
    started_at = models.DateTimeField("시작시각", null=True, blank=True)
    finished_at = models.DateTimeField("종료시각", null=True, blank=True)
    created_at = models.DateTimeField("생성일", auto_now_add=True)

    class Meta:
        verbose_name = "실행작업"
        verbose_name_plural = "실행작업"
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"Job#{self.pk} · sub{self.submission_id} · {self.status}"
