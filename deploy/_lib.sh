# WOOK'S CODING - 배포 스크립트 공용 함수 (source 전용, 단독 실행 아님)
# deploy_main.sh / deploy_worker.sh 가 공유한다.

# ── git: fetch -> (dirty 가드) -> reset --hard origin/<branch> ─────────
# 사용: git_sync <branch> <assume_yes(yes|no)>
git_sync() {
  local branch="$1" assume_yes="$2"
  echo "── git 상태 확인 ─────────────────────────"
  git fetch --prune origin
  git status --short --branch

  if [ -n "$(git status --porcelain)" ] && [ "$assume_yes" != "yes" ]; then
    echo "✖ 커밋되지 않은 변경이 있습니다. 위 변경은 'git reset --hard' 로 사라집니다."
    echo "  강제로 진행하려면 -y 옵션을 붙여 다시 실행하세요."
    exit 1
  fi

  echo "── git reset --hard origin/$branch ───────"
  git reset --hard "origin/$branch"
  echo -n "  현재 커밋: "; git log -1 --oneline
}

# ── .env 값 조회/검증 헬퍼 ────────────────────────────────────────────
# .env 가 없으면 중단. get_env 는 값이 없어도 실패하지 않는다(빈 문자열 반환).
ENV_FAIL=0

env_file_check() {
  [ -f .env ] && return 0
  echo "✖ .env 파일이 없습니다. 'cp .env.example .env' 후 운영값을 채우세요."
  exit 1
}

get_env() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2- || true; }

# require KEY : 빈 값이면 실패 표시(빈 값 gotcha 방지)
require() {
  local val; val="$(get_env "$1")"
  if [ -z "$val" ]; then echo "  ✖ $1 미설정(빈 값)"; ENV_FAIL=1; else echo "  ✓ $1"; fi
}

# warn_placeholder KEY bad1 [bad2 ...] : 예시/기본값 그대로면 경고(중단은 아님)
warn_placeholder() {
  local key="$1"; shift
  local val; val="$(get_env "$key")"
  local bad
  for bad in "$@"; do
    [ "$val" = "$bad" ] && echo "  ⚠ $key 가 예시/기본값('$bad') 입니다. 운영값으로 교체하세요."
  done
}

# 운영은 DJANGO_DEBUG 가 False 여야 함. (빈 값/미설정도 코드상 False 로 동작 → 허용)
require_debug_false() {
  local val; val="$(get_env DJANGO_DEBUG)"
  case "$(printf '%s' "$val" | tr '[:upper:]' '[:lower:]')" in
    ""|false|0|no|off) echo "  ✓ DJANGO_DEBUG='${val}' (운영 OK)" ;;
    *) echo "  ⚠ DJANGO_DEBUG='${val}' — 운영은 False 여야 합니다." ;;
  esac
}

env_check_end() {
  [ "$ENV_FAIL" -eq 0 ] && return 0
  echo "✖ .env 필수값 누락 — 배포를 중단합니다."
  exit 1
}

# ── docker compose 재기동 (빌드 후 변경분만 재생성) ───────────────────
# 사용: compose_up <compose_file>
compose_up() {
  local file="$1"
  echo "── docker compose 재기동 ($file) ─────────"
  docker compose --env-file .env -f "$file" --project-directory . up --build -d
  docker compose --env-file .env -f "$file" --project-directory . ps
}
