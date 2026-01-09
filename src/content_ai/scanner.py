import os
from pathlib import Path
from typing import List

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}


def scan_input(
    input_path: str,
    recursive: bool = False,
    limit: int = None,
    extensions: List[str] = None,
) -> List[Path]:
    """
    Scan input path for video files.

    Args:
        input_path: File or directory path.
        recursive: Whether to search directories recursively.
        limit: Max number of files to return.
        extensions: List of allowed extensions (e.g. ['mp4', 'mov']). If None, uses defaults.

    Returns:
        List of Path objects, sorted alphabetically.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    allowed_exts = set(extensions) if extensions else VIDEO_EXTENSIONS
    # Ensure dots
    allowed_exts = {e if e.startswith(".") else f".{e}" for e in allowed_exts}
    allowed_exts = {e.lower() for e in allowed_exts}

    files = []

    if path.is_file():
        if path.suffix.lower() in allowed_exts:
            files.append(path)
    elif path.is_dir():
        if recursive:
            for root, _, filenames in os.walk(path):
                for name in filenames:
                    p = Path(root) / name
                    if p.suffix.lower() in allowed_exts:
                        files.append(p)
        else:
            for item in path.iterdir():
                if item.is_file() and item.suffix.lower() in allowed_exts:
                    files.append(item)

    # Deterministic sort
    files.sort(key=lambda p: str(p))

    if limit:
        files = files[:limit]

    return files
