import re

from datetime_guard_utils import build_offender_message, find_pattern_offenders, project_root_from_test


NAIVE_NOW_CALL_PATTERN = re.compile(r"datetime\.now\((?!\s*timezone\.utc\s*\))")
NAIVE_DEFAULT_FACTORY_PATTERN = re.compile(r"default_factory\s*=\s*datetime\.now\b")


def test_no_naive_datetime_in_queue_modules():
    root = project_root_from_test(__file__) / "src" / "content_ai"
    queue_root = root / "queue"
    targets = list(queue_root.rglob("*.py")) + [root / "queued_pipeline.py"]

    offenders = find_pattern_offenders(
        targets,
        lambda text: bool(
            NAIVE_NOW_CALL_PATTERN.search(text) or NAIVE_DEFAULT_FACTORY_PATTERN.search(text)
        ),
    )

    assert not offenders, build_offender_message(
        "Use timezone-aware datetime in queue modules and avoid default_factory=datetime.now",
        offenders,
    )
