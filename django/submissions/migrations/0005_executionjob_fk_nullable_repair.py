"""ExecutionJob.user / .submission 의 NOT NULL 제약을 확실히 해제(운영 스키마 드리프트 수리).

배경: 0003 에서 이 두 FK 를 null=True 로 바꾸는 AlterField 가 있으나, 일부 환경(운영)에서
0003 이 '적용됨'으로만 기록되고 실제 `DROP NOT NULL` DDL 이 반영되지 않아 컬럼이 NOT NULL 로
남았다. 그 결과 user/submission 없이 만드는 시스템 잡(code_eval · testcase_gen) INSERT 가
NotNullViolation 으로 500 을 내고, 프론트가 그 비(非)JSON 응답을 파싱하다 실패했다.

이 마이그레이션은 DB 컬럼만 교정한다(모델 상태는 0003 에서 이미 null=True). PostgreSQL 에서
`DROP NOT NULL` 은 이미 nullable 인 컬럼에도 오류 없이 통과하므로 로컬(정상)에서도 멱등 no-op 이다.
역방향은 무 NOT NULL 데이터가 존재할 수 있어 재부여하지 않는다(noop).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0004_alter_executionjob_job_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE submissions_executionjob ALTER COLUMN user_id DROP NOT NULL;"
                "ALTER TABLE submissions_executionjob ALTER COLUMN submission_id DROP NOT NULL;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
