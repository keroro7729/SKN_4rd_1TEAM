"""오답노트 화면 (STEP-03).

권한: 로그인 필요 + 본인 데이터만(§6.1). 저장/AI 분석/RAG 는 STEP-06/07 에서 Fetch 로 연결.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView

from submissions.models import Submission

from .models import WrongNote


class WrongNoteListView(LoginRequiredMixin, ListView):
    """본인 오답노트 목록."""

    template_name = "wrongnotes/wrongnote_list.html"
    context_object_name = "notes"
    paginate_by = 10

    def get_queryset(self):
        return (
            WrongNote.objects.filter(user=self.request.user)
            .select_related("problem")
            .prefetch_related("tags")
            .order_by("-created_at")
        )


class WrongNoteCreateView(LoginRequiredMixin, TemplateView):
    """오답노트 작성 화면. 대상 Submission 은 본인 것만 허용."""

    template_name = "wrongnotes/wrongnote_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        submission = get_object_or_404(
            Submission.objects.select_related("problem"),
            pk=kwargs["submission_id"],
            user=self.request.user,  # 본인 제출만
        )
        ctx["submission"] = submission
        ctx["problem"] = submission.problem
        return ctx


class NoteAskView(LoginRequiredMixin, TemplateView):
    """내 노트에 물어보기 화면 (RAG 호출은 STEP-06/07)."""

    template_name = "wrongnotes/note_ask.html"
