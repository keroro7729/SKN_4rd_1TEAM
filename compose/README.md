# compose/ - 환경별 Docker Compose

배포 환경에 따라 나눠 둔 오케스트레이션 파일 모음. **모든 파일은 레포 루트 기준 상대경로**
(`./django`, `.env`, `./volumes` ...)를 쓰므로 **반드시 레포 루트에서 `--project-directory .` 로 실행**한다.
(compose 는 `-f` 파일이 있는 디렉토리를 프로젝트 루트로 잡기 때문에, 이 옵션이 없으면 `compose/django`
를 찾다가 실패한다.)

## 파일 목록

| 파일 | 용도 | 포함 서비스 | DB |
|---|---|---|---|
| `local.yml` | **개발/테스트** (단일 머신 올인원) | postgres · chromadb · django · fastapi · worker · nginx | 컨테이너 postgres |
| `main.yml` | **운영 - 앱 서버**(EC2) | chromadb · django · fastapi · nginx | **외부 RDS PostgreSQL** |
| `worker.yml` | **운영 - 워커 서버**(별도 EC2) | worker | **외부 RDS PostgreSQL** |

- **local**: postgres 컨테이너를 직접 띄우고 worker 까지 한 번에 올려 로컬에서 전체 흐름을 검증.
- **main / worker**: 운영은 앱 서버와 코드실행 워커를 **다른 EC2 로 분리**하고, DB 는 **RDS 로 외부화**.
  두 서버 모두 `.env` 의 `POSTGRES_HOST` 를 **RDS 엔드포인트**로 맞춰야 한다(아래 참조).

## 실행

먼저 루트 `.env` 준비: `cp .env.example .env` 후 값 채우기 (`../.env.example` 주석 참고).

### 로컬 (개발/테스트)
```bash
# 레포 루트에서
docker compose --env-file .env -f compose/local.yml --project-directory . up --build
# 접속: http://localhost/  (Nginx -> Django)

# 최초 1회: 관리자 계정 / 시드 문제 적재
docker compose --env-file .env -f compose/local.yml --project-directory . exec django python manage.py createsuperuser
docker compose --env-file .env -f compose/local.yml --project-directory . run --rm django python manage.py load_problems

docker compose --env-file .env -f compose/local.yml --project-directory . down       # 중지 (볼륨 유지)
docker compose --env-file .env -f compose/local.yml --project-directory . down -v     # (주의) DB.벡터까지 삭제
```

### 운영 - 앱 서버 EC2
```bash
# .env 의 POSTGRES_HOST 를 RDS 엔드포인트로, DJANGO_DEBUG=False, ALLOWED_HOSTS.SECRET_KEY 세팅
docker compose --env-file .env -f compose/main.yml --project-directory . up --build -d
# 접속: http://<앱서버 도메인/EIP>/
```
- `main.yml` 에는 postgres 서비스가 **없다** -> `django`/`fastapi` 는 `.env` 의 `POSTGRES_HOST`(RDS)로 붙는다.
- `django` 컨테이너 기동 시 `migrate` -> `collectstatic` -> gunicorn 순서로 자동 실행되고,
  `nginx` 는 django healthcheck(`/health/`) 통과 후에만 트래픽을 받는다.

### 운영 - 워커 서버 EC2 (별도 인스턴스)
```bash
# 같은 레포를 워커 EC2 에도 배치, .env 의 POSTGRES_HOST 를 RDS 엔드포인트로 세팅
docker compose --env-file .env -f compose/worker.yml --project-directory . up --build -d
```
- 워커는 RDS 의 `jobs` 테이블을 폴링(`FOR UPDATE SKIP LOCKED`)해 코드 실행을 처리한다.
  `restart: unless-stopped` 로 상시 구동.

## 운영 배포 체크리스트

1. **RDS**: PostgreSQL 인스턴스 생성 -> 보안그룹에서 **앱서버.워커 EC2 만** 5432 인바운드 허용.
2. **`.env`**: `POSTGRES_HOST=<RDS 엔드포인트>` · `DJANGO_DEBUG=False` ·
   `DJANGO_SECRET_KEY`(긴 랜덤) · `DJANGO_ALLOWED_HOSTS`(실도메인/EIP) · `INTERNAL_API_KEY`(강한 랜덤) · `OPENAI_API_KEY`.
3. **앱서버 EC2**: `main.yml` 로 기동. 80 포트만 외부 노출(SG).
4. **워커 EC2**: `worker.yml` 로 기동. 외부 노출 포트 없음.
5. (주의) `local.yml` 은 postgres 5432 를 호스트에 노출한다 -> **운영에서는 절대 사용하지 말 것**
   (운영은 `main`/`worker` 만 사용, DB 는 RDS).

> 상세 규칙: 루트 `CLAUDE.md`, `llm_wiki/4. ...데이터_소유권_및_의존구조.md`
