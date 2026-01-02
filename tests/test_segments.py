import pytest
from content_ai.segments import (
    merge_segments,
    clamp_segments,
    filter_min_duration,
    pad_segments,
)


def test_merge_segments_basic():
    # touching
    segs = [{"start": 0, "end": 1}, {"start": 1, "end": 2}]
    merged = merge_segments(segs, merge_gap=0)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 2


def test_merge_segments_gap():
    # 1s gap, merge_gap=2 -> merge
    segs = [{"start": 0, "end": 1}, {"start": 2, "end": 3}]
    merged = merge_segments(segs, merge_gap=2.0)
    assert len(merged) == 1
    assert merged[0]["end"] == 3

    # 3s gap, merge_gap=2 -> distinct
    segs = [{"start": 0, "end": 1}, {"start": 4, "end": 5}]
    merged = merge_segments(segs, merge_gap=2.0)
    assert len(merged) == 2


def test_merge_overlapping():
    segs = [{"start": 0, "end": 5}, {"start": 2, "end": 3}]
    merged = merge_segments(segs, merge_gap=0)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 5


def test_clamp_segments():
    segs = [{"start": -1, "end": 5}, {"start": 8, "end": 12}]
    clamped = clamp_segments(segs, 0, 10)

    assert clamped[0]["start"] == 0
    assert clamped[0]["end"] == 5

    assert clamped[1]["start"] == 8
    assert clamped[1]["end"] == 10


def test_filter_min_duration():
    segs = [{"start": 0, "end": 0.1}, {"start": 1, "end": 2}]
    filtered = filter_min_duration(segs, 0.5)
    assert len(filtered) == 1
    assert filtered[0]["start"] == 1


def test_pad_segments():
    segs = [{"start": 10, "end": 11}]
    padded = pad_segments(segs, 1.0)
    assert padded[0]["start"] == 9.0
    assert padded[0]["end"] == 12.0
