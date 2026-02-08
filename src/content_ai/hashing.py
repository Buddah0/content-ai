"""Deterministic ID generation for pipeline outputs."""

import hashlib


def deterministic_segment_id(source_path: str, start: float, end: float, score: float) -> str:
    """Generate a content-addressable segment ID.

    The ID is derived from the segment's immutable properties so that
    identical segments always produce identical IDs across runs.

    Args:
        source_path: Path to source video file.
        start: Segment start time in seconds.
        end: Segment end time in seconds.
        score: Segment peak RMS score.

    Returns:
        12-character hexadecimal string.
    """
    content = f"{source_path}:{start:.6f}:{end:.6f}:{score:.6f}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]
