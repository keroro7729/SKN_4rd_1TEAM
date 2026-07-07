"""사용자 코딩 상태 갱신 (수동/스케줄용).

  python manage.py refresh_coding_state <user_id>
  python manage.py refresh_coding_state --all      # 제출 이력이 있는 전체 사용자
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from codingstate.services import refresh
from submissions.models import Submission


class Command(BaseCommand):
    help = "사용자 coding-state(AI 내부 참고값)를 갱신한다."

    def add_arguments(self, parser):
        parser.add_argument("user_id", nargs="?", type=int)
        parser.add_argument("--all", action="store_true", help="제출 이력이 있는 전체 사용자")

    def handle(self, *args, **opts):
        User = get_user_model()
        if opts["all"]:
            user_ids = (
                Submission.objects.filter(submission_type="submit")
                .values_list("user_id", flat=True).distinct()
            )
            users = User.objects.filter(id__in=list(user_ids))
        elif opts["user_id"]:
            users = User.objects.filter(pk=opts["user_id"])
            if not users:
                raise CommandError(f"user {opts['user_id']} 없음")
        else:
            raise CommandError("user_id 또는 --all 필요")

        for user in users:
            state = refresh(user)
            if state:
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] u{user.id} {user.username}: {state.level} · "
                    f"강점 {len(state.strengths)} · 약점 {len(state.weaknesses)}"
                ))
            else:
                self.stdout.write(self.style.WARNING(f"[skip] u{user.id} 갱신 실패/데이터 없음"))
