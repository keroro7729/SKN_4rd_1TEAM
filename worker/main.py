"""WOOK'S CODING - Docker Worker 진입점 (스캐폴딩).

PostgreSQL `jobs` 테이블을 polling 하여 pending Job을 실행한다.
(MVP는 Redis/RabbitMQ 미도입 - Job Table Polling 방식)

Job 상태 생명주기: pending -> running -> success | failed | timeout

STEP-02 실제 테이블명(Django 규칙 <app>_<model>):
  - ExecutionJob -> submissions_executionjob (컬럼: id, submission_id, job_type, status ...)
  - Submission   -> submissions_submission
  - TestCase     -> problems_testcase
아래 SQL은 STEP-02 스키마에 정합돼 있으며, 실제 실행/채점 로직은 STEP-04 에서 채운다.
"""
import time

import psycopg

from config import DB_CONFIG, POLL_INTERVAL_SEC
from logging_setup import setup_logging
from runner import compare_output, run_code

log = setup_logging()


def connect():
    return psycopg.connect(**DB_CONFIG)


def process_one(conn) -> bool:
    """pending Job 1건을 잡아 실행. 처리했으면 True."""
    # FOR UPDATE SKIP LOCKED 로 다중 워커 안전하게 1건 선점
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, submission_id
              FROM submissions_executionjob
             WHERE status = 'pending' AND job_type = 'code_run'
             ORDER BY id
             FOR UPDATE SKIP LOCKED
             LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            return False

        job_id, submission_id = row
        cur.execute(
            "UPDATE submissions_executionjob SET status='running' WHERE id=%s",
            (job_id,),
        )
    conn.commit()

    # TODO(STEP-04): submissions.code / test_cases 조회 -> run_code -> compare_output
    #   결과를 submissions.result 와 jobs.status(success/failed/timeout)에 저장.
    #   Worker 자체 장애는 error_logs에 저장.
    _ = (compare_output, run_code)  # 사용 예정 (STEP-04)
    return True


def main() -> None:
    log.info("started. polling jobs ...")
    while True:
        try:
            with connect() as conn:
                worked = process_one(conn)
            if not worked:
                time.sleep(POLL_INTERVAL_SEC)
        except Exception as exc:  # noqa: BLE001 - 골격: 루프 유지
            log.error("error: %s", exc)
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
