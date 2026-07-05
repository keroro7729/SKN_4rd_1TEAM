"""Wrong note views."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView

from config.pagination import build_pagination_context
from submissions.models import Submission

from .models import WrongNote, WrongNoteQueryLog
from .services import FastAPIClientError, analyze_wrong_note, call_fastapi, embed_wrong_note


class WrongNoteListView(LoginRequiredMixin, ListView):
    """List the authenticated user's wrong notes."""

    template_name = "wrongnotes/wrongnote_list.html"
    context_object_name = "notes"
    paginate_by = 10

    def get_queryset(self):
        return (
            WrongNote.objects.filter(user=self.request.user)
            .select_related("problem", "submission")
            .prefetch_related("tags")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        existing_submission_ids = WrongNote.objects.filter(
            user=self.request.user
        ).values_list("submission_id", flat=True)
        ctx["recent_wrong_submissions"] = (
            Submission.objects.filter(
                user=self.request.user,
                submission_type="submit",
                result__in=["wrong", "error", "timeout"],
            )
            .exclude(id__in=existing_submission_ids)
            .select_related("problem")
            .order_by("-created_at")[:10]
        )
        if ctx.get("page_obj"):
            ctx["pagination"] = build_pagination_context(
                self.request,
                ctx["page_obj"],
            )
        return ctx


class WrongNoteCreateView(LoginRequiredMixin, TemplateView):
    """Create a wrong note from a final failed submission."""

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
        try:
            index_result = embed_wrong_note(note)
            ai_result["index"] = index_result
            note.ai_analysis = ai_result
            note.save(update_fields=["ai_analysis"])
        except FastAPIClientError as exc:
            ai_result.setdefault("errors", []).append(
                {"stage": "embed", "message": str(exc)}
            )
            note.ai_analysis = ai_result
            note.status = "index_failed"
            note.save(update_fields=["ai_analysis", "status"])

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
    """Ask questions against the authenticated user's wrong notes."""

    template_name = "wrongnotes/note_ask.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_logs"] = WrongNoteQueryLog.objects.filter(
            user=self.request.user
        ).order_by("-created_at")[:5]
        return ctx

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error_message": "invalid_json"},
                status=400,
            )

        question = (payload.get("question") or "").strip()
        if not question:
            return JsonResponse(
                {"ok": False, "error_message": "질문을 입력하세요."},
                status=400,
            )

        try:
            result = call_fastapi(
                user=request.user,
                request_type="note_ask",
                path="/ai/wrong-note/ask",
                payload={"user_id": request.user.id, "question": question},
            )
        except FastAPIClientError as exc:
            return JsonResponse(
                {"ok": False, "error_message": str(exc)},
                status=502,
            )

        log = WrongNoteQueryLog.objects.create(
            user=request.user,
            query=question,
            answer=result.get("answer", ""),
            evidence_note_ids=result.get("evidence_note_ids", []),
            scores=result.get("scores", []),
        )
        return JsonResponse(
            {
                "ok": True,
                "query_log_id": log.id,
                "status": result.get("status"),
                "answer": log.answer,
                "evidence_note_ids": log.evidence_note_ids,
                "scores": log.scores,
                "request_id": result.get("request_id"),
            }
        )
