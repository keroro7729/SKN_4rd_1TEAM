#!/usr/bin/env bash
# WOOK'S CODING - 운영 [워커 서버] EC2 배포 스크립트 (코드 실행 전용, 별도 인스턴스)
#   흐름: git fetch/상태확인 -> git reset --hard origin/<branch> -> .env 점검 -> compose/worker.yml 재기동
#   사용: deploy/deploy_worker.sh [branch] [-y]
#     branch : 배포 대상 브랜치 (기본 main)
#     -y     : 커밋 안 된 변경이 있어도 강제로 reset --hard 진행
set -Eeuo pipefail

COMPOSE_FILE="compose/worker.yml"
BRANCH="main"
ASSUME_YES="no"
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES="yes" ;;
    -*)       echo "알 수 없는 옵션: $arg"; exit 2 ;;
    *)        BRANCH="$arg" ;;
  esac
done

cd "$(dirname "$0")/.."
# shellcheck source=deploy/_lib.sh
. "deploy/_lib.sh"
install_error_trap   # 실패를 조용히 넘기지 않고 위치를 출력

echo "▶ [WORKER] repo=$(pwd) | branch=$BRANCH | compose=$COMPOSE_FILE"

git_sync "$BRANCH" "$ASSUME_YES"

echo "── .env 점검 (워커 / RDS 접속) ───────────"
env_file_check
require POSTGRES_HOST          # 운영: RDS 엔드포인트 (앱 서버와 동일)
require POSTGRES_DB
require POSTGRES_USER
require POSTGRES_PASSWORD
warn_placeholder POSTGRES_PASSWORD "password"
env_check_end

compose_up "$COMPOSE_FILE"
echo "✔ [WORKER] 배포 완료 — jobs 폴링 시작 (restart: unless-stopped)"
