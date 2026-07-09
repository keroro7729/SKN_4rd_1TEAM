"""사용자 코딩 상태(AI 내부 참고값).

학습 전과정(제출·채점·오답노트·오류패턴 등)을 집계해 AI 가 요약한 사용자별 실력/학습 상태.
사용자에게 노출하지 않으며, 힌트·오답분석 등 AI 프롬프트의 참고 컨텍스트로만 활용한다.
"""
from django.conf import settings
from django.db import models


class CodingState(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coding_state",
        verbose_name="회원",
    )
    summary = models.TextField("AI 요약", blank=True)
    thinking_profile = models.TextField("사고 추적 메모리", blank=True)
    level = models.CharField("추정 수준", max_length=30, blank=True)
    strengths = models.JSONField("강점", default=list, blank=True)
    weaknesses = models.JSONField("약점", default=list, blank=True)
    recurring_mistakes = models.JSONField("반복 실수", default=list, blank=True)
    recommended_focus = models.JSONField("학습 방향", default=list, blank=True)
    stats_snapshot = models.JSONField("집계 스냅샷", default=dict, blank=True)
    source_submission_count = models.PositiveIntegerField("기준 제출 수", default=0)
    refresh_count = models.PositiveIntegerField("갱신 횟수", default=0)
    model = models.CharField("모델", max_length=64, blank=True)
    created_at = models.DateTimeField("생성", auto_now_add=True)
    updated_at = models.DateTimeField("갱신", auto_now=True)

    class Meta:
        verbose_name = "코딩 상태(AI 내부값)"
        verbose_name_plural = "코딩 상태(AI 내부값)"

    def __str__(self):
        return f"CodingState · u{self.user_id} · {self.level or '미평가'}"
