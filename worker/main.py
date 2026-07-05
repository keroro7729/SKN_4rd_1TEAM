"""WOOK'S CODING - Docker Worker 진입점.

PostgreSQL `jobs` 테이블을 polling 하여 pending Job을 실행한다.
(MVP는 Redis/RabbitMQ 미도입 - Job Table Polling 방식)

Job 상태 생명주기: pending -> running -> success | failed | timeout

STEP-02 실제 테이블명(Django 규칙 <app>_<model>):
  - ExecutionJob -> submissions_executionjob (컬럼: id, submission_id, job_type, status ...)
  - Submission   -> submissions_submission
  - TestCase     -> problems_testcase
아래 SQL은 STEP-02 스키마에 정합된다.
"""
import time
import traceback
import uuid

import psycopg
from psycopg.types.json import Json

from config import DB_CONFIG, POLL_INTERVAL_SEC
from logging_setup import setup_logging
from runner import compare_output, run_code

log = setup_logging()
WORKER_ID = f"worker-{uuid.uuid4().hex[:12]}"


def connect():
    return psycopg.connect(**DB_CONFIG)


def log_system_error(conn, user_id, message: str, exc: Exception) -> None:
    """Worker 시스템 오류를 ErrorLog에 남긴다."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO logs_errorlog
                (user_id, source, level, path, error_type, message, traceback, is_resolved, created_at)
            VALUES
                (%s, 'worker', 'error', 'worker/main.py', %s, %s, %s, false, NOW())
            """,
            (
                user_id,
                exc.__class__.__name__,
                message,
                traceback.format_exc(),
            ),
        )


def fetch_test_cases(cur, problem_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT input_data, expected_output, compare_mode, float_tolerance
          FROM problems_testcase
         WHERE problem_id = %s
         ORDER BY id
         LIMIT 5
        """,
        (problem_id,),
    )
    return [
        {
            "input": row[0] or "",
            "expected": row[1] or "",
            "compare_mode": row[2] or "line_trim",
            "float_tolerance": float(row[3] or 1e-6),
        }
        for row in cur.fetchall()
    ]


def finish_job(conn, job_id: int, submission_id: int, job_status: str, result: str, payload: dict) -> None:
    output = payload.get("stdout", "")
    error_message = payload.get("error_message", "")
    elapsed_ms = payload.get("elapsed_ms")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE submissions_submission
               SET result = %s,
                   output = %s,
                   error_message = %s,
                   elapsed_ms = %s
             WHERE id = %s
            """,
            (result, output, error_message, elapsed_ms, submission_id),
        )
        cur.execute(
            """
            UPDATE submissions_executionjob
               SET status = %s,
                   result_payload = %s,
                   finished_at = NOW()
             WHERE id = %s
            """,
            (job_status, Json(payload), job_id),
        )


def process_one(conn) -> bool:
    """pending Job 1건을 잡아 실행. 처리했으면 True."""
    # FOR UPDATE SKIP LOCKED 로 다중 워커 안전하게 1건 선점
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, submission_id, user_id
              FROM submissions_executionjob
             WHERE status = 'pending' AND job_type IN ('code_run', 'code_submit')
             ORDER BY created_at, id
             FOR UPDATE SKIP LOCKED
             LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            return False

        job_id, submission_id, user_id = row
        cur.execute(
            """
            UPDATE submissions_executionjob
               SET status = 'running',
                   worker_id = %s,
                   started_at = NOW()
             WHERE id = %s
            """,
            (WORKER_ID, job_id),
        )
    conn.commit()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code, problem_id FROM submissions_submission WHERE id = %s",
                (submission_id,),
            )
            submission = cur.fetchone()
            if submission is None:
                raise RuntimeError(f"submission not found: {submission_id}")
            code, problem_id = submission
            test_cases = fetch_test_cases(cur, problem_id)

        if not test_cases:
            payload = {
                "passed": 0,
                "total": 0,
                "stdout": "",
                "stderr": "",
                "error_message": "테스트케이스가 없습니다.",
                "elapsed_ms": 0,
            }
            finish_job(conn, job_id, submission_id, "failed", "error", payload)
            conn.commit()
            return True

        total_elapsed = 0
        passed = 0
        first_stdout = ""
        first_stderr = ""
        first_error = ""
        case_results = []

        for index, case in enumerate(test_cases, start=1):
            run = run_code(code, case["input"])
            total_elapsed += run.get("elapsed_ms") or 0
            first_stdout = first_stdout or run.get("stdout", "")
            first_stderr = first_stderr or run.get("stderr", "")

            if run["timed_out"]:
                first_error = "실행 시간이 초과되었습니다."
                payload = {
                    "passed": passed,
                    "total": len(test_cases),
                    "case_results": case_results,
                    "stdout": first_stdout,
                    "stderr": first_stderr,
                    "error_message": first_error,
                    "elapsed_ms": total_elapsed,
                }
                finish_job(conn, job_id, submission_id, "timeout", "timeout", payload)
                conn.commit()
                return True

            if run["returncode"] != 0:
                first_error = run.get("stderr", "") or "런타임 오류가 발생했습니다."
                payload = {
                    "passed": passed,
                    "total": len(test_cases),
                    "case_results": case_results,
                    "stdout": first_stdout,
                    "stderr": first_stderr,
                    "error_message": first_error,
                    "elapsed_ms": total_elapsed,
                }
                finish_job(conn, job_id, submission_id, "failed", "error", payload)
                conn.commit()
                return True

            ok = compare_output(
                case["expected"],
                run["stdout"],
                case["compare_mode"],
                case["float_tolerance"],
            )
            passed += 1 if ok else 0
            case_results.append({"case": index, "passed": ok})
            if not ok:
                payload = {
                    "passed": passed,
                    "total": len(test_cases),
                    "case_results": case_results,
                    "stdout": first_stdout,
                    "stderr": first_stderr,
                    "error_message": "기대 출력과 다릅니다.",
                    "elapsed_ms": total_elapsed,
                }
                finish_job(conn, job_id, submission_id, "success", "wrong", payload)
                conn.commit()
                return True

        payload = {
            "passed": passed,
            "total": len(test_cases),
            "case_results": case_results,
            "stdout": first_stdout,
            "stderr": first_stderr,
            "error_message": "",
            "elapsed_ms": total_elapsed,
        }
        finish_job(conn, job_id, submission_id, "success", "success", payload)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        with connect() as error_conn:
            log_system_error(error_conn, user_id, f"job_id={job_id}", exc)
            finish_job(
                error_conn,
                job_id,
                submission_id,
                "failed",
                "error",
                {
                    "passed": 0,
                    "total": 0,
                    "stdout": "",
                    "stderr": "",
                    "error_message": "Worker 시스템 오류가 발생했습니다.",
                    "elapsed_ms": 0,
                },
            )
            error_conn.commit()
        log.exception("job failed: %s", job_id)
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
