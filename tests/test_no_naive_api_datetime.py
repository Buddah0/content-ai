import re

from datetime_guard_utils import (
    build_offender_message,
    find_pattern_offenders,
    project_root_from_test,
)

NAIVE_NOW_PATTERN = re.compile(r"datetime\.now\((?!\s*timezone\.utc\s*\))")


def test_no_naive_datetime_now_in_api_modules():
    api_root = project_root_from_test(__file__) / "src" / "content_ai" / "api"
    offenders = find_pattern_offenders(
        api_root.rglob("*.py"),
        lambda text: bool(NAIVE_NOW_PATTERN.search(text)),
    )

    assert not offenders, build_offender_message(
        "Use timezone-aware datetime in API modules (datetime.now(timezone.utc))",
        offenders,
    )
