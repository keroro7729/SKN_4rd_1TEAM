"""WOOK'S CODING - Docker Worker 진입점 (STEP-04).

PostgreSQL submissions_executionjob 테이블을 polling 하여 pending Job을 실행한다.
(MVP는 Redis/RabbitMQ 미도입 - Job Table Polling 방식, FOR UPDATE SKIP LOCKED 로 선점)

Job 상태 생명주기: pending -> running -> success | failed | timeout
실제 테이블명(Django <app>_<model>): submissions_executionjob · submissions_submission · problems_testcase
"""
import time

import psycopg
from psycopg.types.json import Jsonb

from config import DB_CONFIG, POLL_INTERVAL_SEC
from logging_setup import setup_logging
from runner import judge

log = setup_logging()


def connect():
    return psycopg.connect(**DB_CONFIG)


def process_one(conn) -> bool:
    """pending Job 1건을 잡아 실행/채점. 처리했으면 True."""
    # 1) pending Job 1건 선점 (다중 워커 안전)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, submission_id, input_payload
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
        job_id, submission_id, input_payload = row
        cur.execute(
            "UPDATE submissions_executionjob SET status='running', started_at=NOW() WHERE id=%s",
            (job_id,),
        )
    conn.commit()

    try:
        # 2) 제출 코드 + 문제의 테스트케이스 조회
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code, problem_id FROM submissions_submission WHERE id=%s",
                (submission_id,),
            )
            sub = cur.fetchone()
            if sub is None:
                raise RuntimeError(f"submission {submission_id} not found")
            code, problem_id = sub

            cur.execute(
                """
                SELECT input_data, expected_output, compare_mode, float_tolerance
                  FROM problems_testcase
                 WHERE problem_id = %s
                 ORDER BY id
                """,
                (problem_id,),
            )
            test_cases = [
                {
                    "input_data": r[0],
                    "expected_output": r[1],
                    "compare_mode": r[2],
                    "float_tolerance": r[3],
                }
                for r in cur.fetchall()
            ]

        # 3) 채점 — 실행(run): 1번 테스트케이스만 / 제출(submit): 전체
        mode = (input_payload or {}).get("mode", "submit")
        cases = test_cases[:1] if mode == "run" else test_cases
        v = judge(code, cases)

        result_payload = {
            "mode": mode,
            "result": v["result"],
            "passed": v["passed"],
            "total": v["total"],
        }
        if mode == "run":  # UI 표시용: 입력/기대정답/실행결과
            tc0 = cases[0] if cases else {}
            result_payload["input"] = tc0.get("input_data") or ""
            result_payload["expected"] = tc0.get("expected_output") or ""
            result_payload["actual"] = v["output"]

        # 4) 결과 저장: Submission.result(사용자용) + ExecutionJob.status(운영용)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submissions_submission
                   SET result=%s, output=%s, error_message=%s, elapsed_ms=%s
                 WHERE id=%s
                """,
                (v["result"], v["output"][:10000], v["error_message"][:5000],
                 v["elapsed_ms"], submission_id),
            )
            cur.execute(
                """
                UPDATE submissions_executionjob
                   SET status=%s, result_payload=%s, finished_at=NOW()
                 WHERE id=%s
                """,
                (v["job_status"], Jsonb(result_payload), job_id),
            )
        conn.commit()
        log.info(
            "job %s (sub %s) [%s] -> %s  %s/%s  %sms",
            job_id, submission_id, mode, v["result"], v["passed"], v["total"], v["elapsed_ms"],
        )
    except Exception as exc:  # noqa: BLE001 - Worker 자체 장애: job=failed 로 마크하고 루프 유지
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE submissions_executionjob SET status='failed', finished_at=NOW() WHERE id=%s",
                (job_id,),
            )
            cur.execute(
                "UPDATE submissions_submission SET result='error', error_message=%s WHERE id=%s",
                (f"worker error: {exc}"[:5000], submission_id),
            )
        conn.commit()
        log.error("job %s failed: %s", job_id, exc)
    return True


def main() -> None:
    log.info("started. polling jobs ...")
    while True:
        try:
            with connect() as conn:
                worked = process_one(conn)
            if not worked:
                time.sleep(POLL_INTERVAL_SEC)
        except Exception as exc:  # noqa: BLE001 - 연결 장애 등: 루프 유지
            log.error("loop error: %s", exc)
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
