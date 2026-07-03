#!/usr/bin/env python
"""Django 관리 명령 실행 진입점."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django를 불러오지 못했습니다. 가상환경이 활성화되어 있고 "
            "requirements.txt가 설치되어 있는지 확인하세요."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
