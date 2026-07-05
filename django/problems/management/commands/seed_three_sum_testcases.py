from django.core.management.base import BaseCommand, CommandError
from problems.models import Problem, TestCase


class Command(BaseCommand):
    help = "세 수의 합 찾기 문제에 테스트케이스를 추가합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            default="세 수의 합",
            help="테스트케이스를 추가할 문제 제목 검색어",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="기존 테스트케이스를 삭제하고 다시 생성합니다.",
        )

    def handle(self, *args, **options):
        title = options["title"]
        replace = options["replace"]

        problem = Problem.objects.filter(title__icontains=title).first()

        if not problem:
            raise CommandError(f"'{title}' 제목을 포함하는 문제를 찾을 수 없습니다.")

        fk_field = self.get_problem_fk_field()
        input_field = self.get_first_existing_field(
            TestCase,
            [
                "input_data",
                "input_text",
                "input",
                "stdin",
                "input_value",
                "input_content",
            ],
        )
        output_field = self.get_first_existing_field(
            TestCase,
            [
                "expected_output",
                "expected_stdout",
                "output_data",
                "output_text",
                "output",
                "stdout",
                "answer",
            ],
        )

        if not input_field or not output_field:
            fields = [f.name for f in TestCase._meta.fields]
            raise CommandError(
                "TestCase 입력/출력 필드명을 찾지 못했습니다. "
                f"현재 필드: {fields}"
            )

        queryset = TestCase.objects.filter(**{fk_field: problem})
        old_count = queryset.count()

        if old_count > 0 and not replace:
            self.stdout.write(
                self.style.WARNING(
                    f"이미 테스트케이스가 {old_count}개 있습니다. "
                    "다시 만들려면 --replace 옵션을 사용하세요."
                )
            )
            return

        if replace:
            queryset.delete()

        testcases = [
            {
                "input": "5\n1 2 3 4 5\n9\n",
                "output": "True\n",
            },
            {
                "input": "3\n1 2 3\n10\n",
                "output": "False\n",
            },
            {
                "input": "6\n5 7 1 2 9 4\n12\n",
                "output": "True\n",
            },
            {
                "input": "4\n10 20 30 40\n60\n",
                "output": "True\n",
            },
            {
                "input": "4\n10 20 30 40\n100\n",
                "output": "False\n",
            },
            {
                "input": "4\n1 1 1 2\n3\n",
                "output": "True\n",
            },
        ]

        created = 0

        for index, case in enumerate(testcases, start=1):
            kwargs = {
                fk_field: problem,
                input_field: case["input"],
                output_field: case["output"],
            }

            self.apply_optional_fields(kwargs, index)

            TestCase.objects.create(**kwargs)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"문제 ID={problem.id}, 제목='{problem.title}'에 "
                f"테스트케이스 {created}개를 생성했습니다."
            )
        )

    def get_problem_fk_field(self):
        for field in TestCase._meta.fields:
            remote_model = getattr(field.remote_field, "model", None)
            if remote_model == Problem:
                return field.name

        raise CommandError("TestCase에서 Problem ForeignKey 필드를 찾지 못했습니다.")

    def get_first_existing_field(self, model, candidates):
        model_fields = {field.name for field in model._meta.fields}

        for candidate in candidates:
            if candidate in model_fields:
                return candidate

        return None

    def apply_optional_fields(self, kwargs, index):
        model_fields = {field.name for field in TestCase._meta.fields}

        if "order" in model_fields:
            kwargs["order"] = index

        if "case_no" in model_fields:
            kwargs["case_no"] = index

        if "is_sample" in model_fields:
            kwargs["is_sample"] = index <= 2

        if "sample" in model_fields:
            kwargs["sample"] = index <= 2

        if "match_type" in model_fields:
            kwargs["match_type"] = "line_trim"

        if "comparison_type" in model_fields:
            kwargs["comparison_type"] = "line_trim"

        if "compare_type" in model_fields:
            kwargs["compare_type"] = "line_trim"

        if "judge_type" in model_fields:
            kwargs["judge_type"] = "line_trim"