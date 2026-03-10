from datetime_guard_utils import build_offender_message, find_pattern_offenders, project_root_from_test


def test_no_datetime_utcnow_in_src():
    src_root = project_root_from_test(__file__) / "src"
    offenders = find_pattern_offenders(
        src_root.rglob("*.py"),
        lambda text: "datetime.utcnow(" in text,
    )

    assert not offenders, build_offender_message(
        "datetime.utcnow() is deprecated; use datetime.now(timezone.utc)",
        offenders,
    )
