"""사용자 코딩 상태 갱신 (수동/스케줄용).

  python manage.py refresh_coding_state <user_id>          # 단일 사용자 강제 갱신
  python manage.py refresh_coding_state --stale            # 신규 활동 쌓인 사용자만 배치 갱신
  python manage.py refresh_coding_state --stale --min-new 3 --limit 50
  python manage.py refresh_coding_state --all              # 제출 이력이 있는 전체 강제 갱신

⚠️ 배치는 사용자당 FastAPI(LLM) 동기 호출을 하므로 순차·저속이다(요청 경로 아님, 크론/수동 전용).
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from codingstate.services import batch_refresh, refresh


class Command(BaseCommand):
    help = "사용자 coding-state(AI 내부 참고값)를 갱신한다."

    def add_arguments(self, parser):
        parser.add_argument("user_id", nargs="?", type=int)
        parser.add_argument("--all", action="store_true", help="제출 이력 전체 강제 갱신")
        parser.add_argument("--stale", action="store_true", help="신규 활동이 쌓인 사용자만 배치 갱신")
        parser.add_argument("--min-new", type=int, default=5, help="--stale 기준: 신규 제출 최소 건수(기본 5)")
        parser.add_argument("--limit", type=int, default=None, help="배치 1회 최대 갱신 사용자 수")

    def handle(self, *args, **opts):
        if opts["stale"] or opts["all"]:
            summary = batch_refresh(
                min_new_submissions=opts["min_new"],
                limit=opts["limit"],
                force=opts["all"],  # --all 은 staleness 무시 강제 갱신
                log=self.stdout.write,
            )
            self.stdout.write(self.style.SUCCESS(
                f"[batch] 후보 {summary['candidates']} · stale {summary['stale']} · "
                f"처리 {summary['processed']} · 갱신 {summary['refreshed']} · "
                f"실패 {summary['failed']} · fresh스킵 {summary['skipped_fresh']}"
            ))
            return

        if not opts["user_id"]:
            raise CommandError("user_id, --stale, 또는 --all 필요")

        user = get_user_model().objects.filter(pk=opts["user_id"]).first()
        if user is None:
            raise CommandError(f"user {opts['user_id']} 없음")

        state = refresh(user)
        if state:
            self.stdout.write(self.style.SUCCESS(
                f"[OK] u{user.id} {user.username}: {state.level} · "
                f"강점 {len(state.strengths)} · 약점 {len(state.weaknesses)}"
            ))
        else:
            self.stdout.write(self.style.WARNING(f"[skip] u{user.id} 갱신 실패/데이터 없음"))
