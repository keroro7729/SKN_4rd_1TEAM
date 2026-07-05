"""오답노트 화면."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView

from submissions.models import Submission

from .models import WrongNote
from .services import analyze_wrong_note


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

    def get_submission(self):
        return get_object_or_404(
            Submission.objects.select_related("problem"),
            pk=self.kwargs["submission_id"],
            user=self.request.user,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        submission = self.get_submission()
        ctx["submission"] = submission
        ctx["problem"] = submission.problem
        return ctx

    def post(self, request, *args, **kwargs):
        submission = self.get_submission()
        if submission.submission_type != "submit":
            return JsonResponse(
                {
                    "ok": False,
                    "error_message": "최종 제출 결과만 오답노트로 저장할 수 있습니다.",
                },
                status=400,
            )
        if submission.result not in {"wrong", "error", "timeout"}:
            return JsonResponse(
                {
                    "ok": False,
                    "error_message": "오답, 오류, 시간초과 제출만 오답노트로 저장할 수 있습니다.",
                },
                status=400,
            )

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error_message": "invalid_json"},
                status=400,
            )

        comment = (payload.get("comment") or "").strip()
        if not comment:
            return JsonResponse(
                {"ok": False, "error_message": "코멘트를 입력하세요."},
                status=400,
            )

        note = (
            WrongNote.objects.filter(user=request.user, submission=submission)
            .order_by("-id")
            .first()
        )
        if note is None:
            note = WrongNote.objects.create(
                user=request.user,
                submission=submission,
                problem=submission.problem,
                comment=comment,
                status="completed",
            )
        note.problem = submission.problem
        note.comment = comment
        note.status = "completed"
        note.save(update_fields=["problem", "comment", "status"])
        note.tags.set(submission.problem.tags.all())

        ai_result = analyze_wrong_note(note)
        note.ai_analysis = ai_result
        note.save(update_fields=["ai_analysis"])

        return JsonResponse(
            {
                "ok": True,
                "wrong_note_id": note.id,
                "status": note.status,
                "ai_analysis": ai_result,
                "list_url": "/wrongnotes/",
            },
            status=201,
        )


class NoteAskView(LoginRequiredMixin, TemplateView):
    """내 노트에 물어보기 화면 (RAG 호출은 STEP-06/07)."""

    template_name = "wrongnotes/note_ask.html"
