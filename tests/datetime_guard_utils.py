from pathlib import Path
from typing import Callable, Iterable, List


def project_root_from_test(test_file: str) -> Path:
    return Path(test_file).resolve().parents[1]


def find_pattern_offenders(files: Iterable[Path], predicate: Callable[[str], bool]) -> List[str]:
    offenders: List[str] = []
    for py_file in files:
        text = py_file.read_text(encoding="utf-8")
        if predicate(text):
            offenders.append(str(py_file))
    return offenders


def build_offender_message(prefix: str, offenders: Iterable[str]) -> str:
    return f"{prefix}: {', '.join(offenders)}"
