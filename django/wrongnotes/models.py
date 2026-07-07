"""오답노트 모델 (지시문 §7): WrongNote · WrongNoteVector · WrongNoteQueryLog.

- WrongNote: 원문/사용자코멘트/AI분석(JSON). status draft→completed→indexed.
- WrongNoteVector: ChromaDB(wrong_note_embeddings) 인덱싱 메타 (원문 1:1). 실제 벡터는 ChromaDB.
- WrongNoteQueryLog: '내 노트에 물어보기' 질의/답변/근거 로그.
설계 상세: llm_wiki/6. ...데이터모델_문제_제출_Job_오답노트_v0.1.md §4
"""
from django.conf import settings
from django.db import models

from config.choices import WRONG_NOTE_STATUS_CHOICES
from problems.models import Problem, ProblemTag
from submissions.models import Submission


class WrongNote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wrong_notes",
        verbose_name="회원",
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="wrong_notes",
        verbose_name="문제",
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="wrong_notes",
        verbose_name="제출",
    )
    tags = models.ManyToManyField(
        ProblemTag, blank=True, related_name="wrong_notes", verbose_name="태그"
    )
    comment = models.TextField("사용자코멘트", blank=True)
    ai_analysis = models.JSONField("AI분석", default=dict, blank=True)
    error_pattern = models.CharField("오류패턴", max_length=100, blank=True)
    status = models.CharField(
        "상태", max_length=20, choices=WRONG_NOTE_STATUS_CHOICES, default="draft"
    )
    is_reviewed = models.BooleanField("복습완료", default=False)
    is_review_hidden = models.BooleanField("복습보드숨김", default=False)
    reviewed_at = models.DateTimeField("복습일", null=True, blank=True)
    created_at = models.DateTimeField("작성일", auto_now_add=True)

    class Meta:
        verbose_name = "오답노트"
        verbose_name_plural = "오답노트"
        indexes = [models.Index(fields=["user", "status", "created_at"])]

    def __str__(self):
        return f"WrongNote#{self.pk} · u{self.user_id} · {self.status}"


class WrongNoteVector(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wrong_note_vectors",
        verbose_name="회원",
    )
    wrong_note = models.OneToOneField(
        WrongNote,
        on_delete=models.CASCADE,
        related_name="vector",
        verbose_name="오답노트",
    )
    embedding_id = models.CharField("임베딩ID", max_length=128)
    source = models.CharField("출처", max_length=30, default="wrong_note")
    indexed_at = models.DateTimeField("인덱싱시각", null=True, blank=True)

    class Meta:
        verbose_name = "오답노트 벡터"
        verbose_name_plural = "오답노트 벡터"
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"Vector · note{self.wrong_note_id}"


class WrongNoteQueryLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="note_query_logs",
        verbose_name="회원",
    )
    query = models.TextField("질의")
    answer = models.TextField("답변", blank=True)
    evidence_note_ids = models.JSONField("근거노트ID", default=list, blank=True)
    scores = models.JSONField("점수", default=list, blank=True)
    created_at = models.DateTimeField("생성일", auto_now_add=True)

    class Meta:
        verbose_name = "내 노트 질의 로그"
        verbose_name_plural = "내 노트 질의 로그"
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"QueryLog#{self.pk} · u{self.user_id}"
