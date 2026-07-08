"""Wrong note views."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from config.pagination import build_pagination_context
from gamification.services import record_user_action
from submissions.models import Submission

from .models import WrongNote
from .services import FastAPIClientError, analyze_wrong_note, call_fastapi, embed_wrong_note


class WrongNoteListView(LoginRequiredMixin, ListView):
    """List the authenticated user's wrong notes."""

    template_name = "wrongnotes/wrongnote_list.html"
    context_object_name = "notes"
    paginate_by = 10

    def get_queryset(self):
        self.f_q = (self.request.GET.get("q") or "").strip()
        self.f_status = self.request.GET.get("status") or ""
        qs = (
            WrongNote.objects.filter(user=self.request.user)
            .select_related("problem", "submission")
            .prefetch_related("tags")
        )
        if self.f_q:
            qs = qs.filter(problem__title__icontains=self.f_q)

        # 복습보드에서 제거한 노트는 기본 목록에서 숨깁니다.
        # 오답노트 원본은 삭제하지 않고, hidden 필터에서 다시 확인/복원할 수 있습니다.
        if self.f_status == "hidden":
            qs = qs.filter(is_review_hidden=True)
        else:
            qs = qs.filter(is_review_hidden=False)
            if self.f_status == "reviewed":
                qs = qs.filter(is_reviewed=True)
            elif self.f_status == "unreviewed":
                qs = qs.filter(is_reviewed=False)
            elif self.f_status:
                qs = qs.filter(status=self.f_status)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        notes_all = WrongNote.objects.filter(user=self.request.user)
        visible_notes = notes_all.filter(is_review_hidden=False)
        existing_submission_ids = notes_all.values_list("submission_id", flat=True)
        ctx["note_stats"] = {
            "total": visible_notes.count(),
            "unreviewed": visible_notes.filter(is_reviewed=False).count(),
            "reviewed": visible_notes.filter(is_reviewed=True).count(),
            "indexed": visible_notes.filter(status="indexed").count(),
            "hidden": notes_all.filter(is_review_hidden=True).count(),
        }
        ctx["q"] = self.f_q
        ctx["cur_status"] = self.f_status
        ctx["status_filters"] = [
            ("", "전체"),
            ("unreviewed", "미해결"),
            ("reviewed", "해결 완료"),
            ("indexed", "인덱싱 완료"),
            ("index_failed", "인덱싱 실패"),
            ("hidden", "보드에서 제거됨"),
        ]
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
        ctx["recent_notes"] = (
            visible_notes.select_related("problem").order_by("-created_at")[:5]
        )
        ctx["pattern_rows"] = (
            visible_notes.exclude(error_pattern="")
            .values("error_pattern")
            .annotate(count=Count("id"))
            .order_by("-count")[:4]
        )
        ctx["suggested_questions"] = [
            "내가 어떤 유형에서 자주 틀렸지?",
            "최근 반복되는 실수 패턴은?",
            "DP 문제 약점 정리해줘",
        ]
        if ctx.get("page_obj"):
            ctx["pagination"] = build_pagination_context(
                self.request,
                ctx["page_obj"],
            )
        return ctx


class WrongNoteDetailView(LoginRequiredMixin, DetailView):
    """Show one wrong note owned by the authenticated user."""

    template_name = "wrongnotes/wrongnote_detail.html"
    context_object_name = "note"
    pk_url_kwarg = "note_id"

    def get_queryset(self):
        return (
            WrongNote.objects.filter(user=self.request.user)
            .select_related("problem", "submission")
            .prefetch_related("tags")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        note = self.object
        ctx["analysis"] = note.ai_analysis.get("analysis", {}) if note.ai_analysis else {}
        ctx["similar_notes"] = note.ai_analysis.get("similar_notes", []) if note.ai_analysis else []
        ctx["analysis_errors"] = note.ai_analysis.get("errors", []) if note.ai_analysis else []
        try:
            ctx["vector"] = note.vector
        except WrongNote.vector.RelatedObjectDoesNotExist:
            ctx["vector"] = None
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
        ctx["similar_recent_notes"] = (
            WrongNote.objects.filter(
                user=self.request.user,
                problem__tags__in=submission.problem.tags.all(),
            )
            .exclude(submission=submission)
            .select_related("problem")
            .prefetch_related("tags")
            .distinct()
            .order_by("-created_at")[:3]
        )
        # Front UX: show the user's previous submissions for the same problem
        # so the reflection page can compare current code with past attempts.
        ctx["submission_history"] = (
            Submission.objects.filter(
                user=self.request.user,
                problem=submission.problem,
                submission_type="submit",
            )
            .exclude(pk=submission.pk)
            .order_by("-created_at")[:8]
        )
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
        record_user_action(request.user, "wrongnote_completed", note)

        # 학습 이벤트 훅: 코딩 상태(AI 내부 참고값) 자동 갱신(제출이 충분히 쌓였을 때만).
        try:
            from codingstate.services import ensure_fresh

            ensure_fresh(request.user)
        except Exception:  # noqa: BLE001 - 상태 갱신 실패가 노트 저장을 막지 않도록
            pass

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


@login_required
@require_POST
def review_wrong_note(request, note_id):
    """Mark a wrong note as reviewed and award review points once."""
    note = get_object_or_404(WrongNote, pk=note_id, user=request.user)
    if not note.is_reviewed:
        note.is_reviewed = True
        note.reviewed_at = timezone.now()
        note.save(update_fields=["is_reviewed", "reviewed_at"])
        reward = record_user_action(request.user, "review_completed", note)
        point_created = reward["point_created"]
    else:
        point_created = False

    return JsonResponse(
        {
            "ok": True,
            "wrong_note_id": note.id,
            "is_reviewed": note.is_reviewed,
            "reviewed_at": note.reviewed_at.isoformat() if note.reviewed_at else None,
            "point_created": point_created,
            "user_point": request.user.point,
        }
    )


@login_required
@require_POST
def hide_from_review_board(request, note_id):
    """Hide a wrong note from the review board without deleting the note."""
    note = get_object_or_404(WrongNote, pk=note_id, user=request.user)
    if not note.is_review_hidden:
        note.is_review_hidden = True
        note.save(update_fields=["is_review_hidden"])

    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "wrongnotes:list")


@login_required
@require_POST
def restore_to_review_board(request, note_id):
    """Restore a hidden wrong note to the review board."""
    note = get_object_or_404(WrongNote, pk=note_id, user=request.user)
    if note.is_review_hidden:
        note.is_review_hidden = False
        note.save(update_fields=["is_review_hidden"])

    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "wrongnotes:list")
