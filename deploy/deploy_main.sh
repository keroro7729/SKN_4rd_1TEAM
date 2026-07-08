#!/usr/bin/env bash
# WOOK'S CODING - 운영 [앱 서버] EC2 배포 스크립트
#   흐름: git fetch/상태확인 -> git reset --hard origin/<branch> -> .env 점검 -> compose/main.yml 재기동
#   사용: deploy/deploy_main.sh [branch] [-y]
#     branch : 배포 대상 브랜치 (기본 main)
#     -y     : 커밋 안 된 변경이 있어도 강제로 reset --hard 진행
set -euo pipefail

COMPOSE_FILE="compose/main.yml"
BRANCH="main"
ASSUME_YES="no"
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES="yes" ;;
    -*)       echo "알 수 없는 옵션: $arg"; exit 2 ;;
    *)        BRANCH="$arg" ;;
  esac
done

# 레포 루트로 이동 (이 스크립트는 deploy/ 하위에 있다) 후 공용 함수 로드
cd "$(dirname "$0")/.."
# shellcheck source=deploy/_lib.sh
. "deploy/_lib.sh"

echo "▶ [APP] repo=$(pwd) | branch=$BRANCH | compose=$COMPOSE_FILE"

git_sync "$BRANCH" "$ASSUME_YES"

echo "── .env 점검 (앱 서버 / RDS) ─────────────"
env_file_check
require POSTGRES_HOST          # 운영: RDS 엔드포인트
require POSTGRES_PASSWORD
require DJANGO_SECRET_KEY
require DJANGO_ALLOWED_HOSTS
require INTERNAL_API_KEY
require OPENAI_API_KEY
warn_placeholder DJANGO_SECRET_KEY "change-me-to-a-long-random-string"
warn_placeholder INTERNAL_API_KEY  "dev-internal-key"
warn_placeholder POSTGRES_PASSWORD "password"
require_debug_false
env_check_end

compose_up "$COMPOSE_FILE"
echo "✔ [APP] 배포 완료 — http://<앱서버 도메인/EIP>/"
