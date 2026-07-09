# WOOK'S CODING - 배포 스크립트 공용 함수 (source 전용, 단독 실행 아님)
# deploy_main.sh / deploy_worker.sh 가 공유한다.

# ── 실패를 '조용히' 넘기지 않게 하는 에러 트랩 ────────────────────────
# set -e 로 스크립트가 아무 메시지 없이 종료되던 문제 방지. 어떤 명령이 실패해도
# 실패 위치/명령/종료코드를 출력하고 종료한다. 스크립트 상단에서 install_error_trap 호출.
_deploy_on_error() {
  local code="$1" cmd="$2" src="$3" line="$4"
  {
    echo ""
    echo "✖ 배포 중단 — 명령이 실패했습니다."
    echo "  위치 : ${src##*/}:${line}  (함수: ${FUNCNAME[2]:-main})"
    echo "  명령 : ${cmd}"
    echo "  코드 : ${code}"
  } >&2
  exit "$code"
}

install_error_trap() {
  # -E: ERR 트랩을 함수/서브셸까지 상속(이게 없으면 함수 안 실패가 조용히 샘)
  set -Eeuo pipefail
  trap '_deploy_on_error "$?" "$BASH_COMMAND" "${BASH_SOURCE[0]}" "$LINENO"' ERR
}

# ── git: fetch -> (dirty 가드) -> reset --hard origin/<branch> ─────────
# 사용: git_sync <branch> <assume_yes(yes|no)>
git_sync() {
  local branch="$1" assume_yes="$2"
  echo "── git 상태 확인 ─────────────────────────"
  git fetch --prune origin
  git status --short --branch

  if [ -n "$(git status --porcelain)" ] && [ "$assume_yes" != "yes" ]; then
    echo "✖ 커밋되지 않은 변경이 있습니다. 위 변경은 'git reset --hard' 로 사라집니다."
    echo "  ⚠ 특히 새 마이그레이션 파일이 여기 있으면 유실되어 배포에 반영되지 않습니다."
    echo "    → 먼저 commit & push 하세요. 그래도 강제 진행하려면 -y 옵션을 붙이세요."
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

# .env 에서 KEY 값만 추출. 없으면 빈 문자열(실패로 스크립트를 종료시키지 않음).
# 파이프라인+cut 대신 파라미터 확장을 써서 set -e/pipefail 에 안전하고,
# 윈도우 CRLF 로 편집된 .env 의 뒤 CR(\r) 을 제거해 값 비교가 어긋나지 않게 한다.
get_env() {
  local line val
  line="$(grep -E "^$1=" .env 2>/dev/null | tail -n1 || true)"
  val="${line#*=}"       # 첫 '=' 뒤 전체 (매치 없으면 빈 문자열)
  val="${val%$'\r'}"     # 뒤쪽 CR 제거
  printf '%s' "$val"
}

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
        if [ "$val" = "$bad" ]; then
            echo "  ⚠ $key 가 예시/기본값('$bad') 입니다. 운영값으로 교체하세요."
        fi
    done

    return 0
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

# ── 배포 검증: Django 가 실제로 기동됐는지(= migrate 성공 포함) 확인 ──
# django command 는 `migrate && collectstatic && gunicorn` 이라 migrate 실패 시
# 컨테이너가 exited 로 죽는다. 여기서 health 를 기다려 실패를 '조용히'가 아니라 드러낸다.
verify_app() {
  local file="$1" cid status tries=0
  echo "── 배포 검증: Django 헬스 대기 (마이그레이션 성공 여부 포함) ──"
  cid="$(docker compose --env-file .env -f "$file" --project-directory . ps -q django 2>/dev/null || true)"
  if [ -z "$cid" ]; then
    echo "  ✖ django 컨테이너가 생성되지 않았습니다."
    return 1
  fi
  while [ "$tries" -lt 40 ]; do
    status="$(docker inspect -f '{{ if .State.Health }}h:{{ .State.Health.Status }}{{ else }}s:{{ .State.Status }}{{ end }}' "$cid" 2>/dev/null || echo unknown)"
    case "$status" in
      h:healthy)                    echo "  ✓ Django healthy — 마이그레이션·기동 정상"; return 0 ;;
      s:running)                    echo "  ✓ Django running (healthcheck 미정의)"; return 0 ;;
      h:unhealthy|s:exited|s:dead)  break ;;
      *)                            : ;;   # h:starting 등은 계속 대기
    esac
    sleep 3; tries=$((tries + 1))
  done
  echo "  ✖ Django 기동 실패/지연 (status=${status:-unknown})."
  echo "  ── migrate.log 마지막 30줄 (마이그레이션 실패 여부 확인) ──"
  tail -n 30 volumes/logs/django/migrate.log 2>/dev/null || echo "    (migrate.log 없음)"
  echo "  ── django 컨테이너 최근 로그 ──"
  docker compose --env-file .env -f "$file" --project-directory . logs --tail 20 django 2>/dev/null || true
  return 1
}
