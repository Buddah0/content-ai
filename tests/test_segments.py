from content_ai.segments import (
    clamp_segments,
    filter_min_duration,
    merge_segments,
    pad_segments,
)

# ============================================================================
# Smart Merging Tests (with max_duration enforcement)
# ============================================================================


def test_merge_with_max_duration_simple():
    """Test that segments merge correctly when under max_duration."""
    segs = [
        {"start": 0, "end": 2, "score": 0.5},
        {"start": 2.5, "end": 4, "score": 0.6},  # gap=0.5s
    ]
    # merge_gap=1.0 allows merge, max_duration=5.0 allows merge (total would be 4s)
    merged = merge_segments(segs, merge_gap=1.0, max_duration=5.0)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 4
    assert merged[0]["score"] == 0.6  # max score


def test_merge_exceeds_max_duration_keeps_louder():
    """Test that when merge would exceed max_duration, louder segment is kept."""
    segs = [
        {"start": 0, "end": 6, "score": 0.5},  # 6s duration
        {"start": 7, "end": 9, "score": 0.8},  # 2s duration, gap=1s
    ]
    # merge_gap=2.0 allows merge, but merged duration would be 9s > max_duration=8s
    # Should keep the second segment (higher score)
    merged = merge_segments(segs, merge_gap=2.0, max_duration=8.0)
    assert len(merged) == 2
    # Both segments should be present since we can't merge
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 6
    assert merged[1]["start"] == 7
    assert merged[1]["end"] == 9


def test_merge_exceeds_max_duration_deterministic_tie():
    """Test deterministic tie-breaking when scores are equal."""
    segs = [
        {"start": 0, "end": 6, "score": 0.7},
        {"start": 7, "end": 9, "score": 0.7},  # Equal score
    ]
    # merge_gap=2.0, max_duration=8.0 -> would merge to 9s, exceeds limit
    # With equal scores, should keep first encountered (deterministic)
    merged = merge_segments(segs, merge_gap=2.0, max_duration=8.0)
    assert len(merged) == 2


def test_merge_gap_boundary_cases():
    """Test merging behavior exactly at and around merge_gap boundary."""
    # Gap exactly at merge_gap
    segs = [{"start": 0, "end": 1}, {"start": 3, "end": 4}]  # gap=2.0
    merged = merge_segments(segs, merge_gap=2.0)
    assert len(merged) == 1  # gap <= merge_gap, should merge

    # Gap just over merge_gap
    segs = [{"start": 0, "end": 1}, {"start": 3.1, "end": 4}]  # gap=2.1
    merged = merge_segments(segs, merge_gap=2.0)
    assert len(merged) == 2  # gap > merge_gap, should NOT merge


def test_merge_three_consecutive_segments():
    """Test merging 3+ consecutive segments within merge_gap."""
    segs = [
        {"start": 0, "end": 1, "score": 0.5},
        {"start": 1.5, "end": 2.5, "score": 0.6},  # gap=0.5
        {"start": 3, "end": 4, "score": 0.7},  # gap=0.5
    ]
    # All gaps within merge_gap=1.0, total duration=4s < max_duration=10s
    merged = merge_segments(segs, merge_gap=1.0, max_duration=10.0)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 4
    assert merged[0]["score"] == 0.7  # highest score


def test_merge_with_overlapping_segments():
    """Test that overlapping segments merge correctly."""
    segs = [
        {"start": 0, "end": 5, "score": 0.5},
        {"start": 3, "end": 6, "score": 0.8},  # overlaps
    ]
    merged = merge_segments(segs, merge_gap=0, max_duration=10.0)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 6
    assert merged[0]["score"] == 0.8


def test_merge_padding_overlap():
    """Test segments that overlap after padding is applied."""
    # Simulate padded segments (padding happens before merge in pipeline)
    segs = [
        {"start": 1, "end": 3, "score": 0.5},  # original event at 2s ± 1s padding
        {"start": 3.5, "end": 5.5, "score": 0.6},  # original event at 4.5s ± 1s padding
    ]
    # Gap is 0.5s, merge_gap=1.0 should merge
    merged = merge_segments(segs, merge_gap=1.0, max_duration=10.0)
    assert len(merged) == 1
    assert merged[0]["start"] == 1
    assert merged[0]["end"] == 5.5


def test_merge_no_max_duration_constraint():
    """Test merging without max_duration constraint (None)."""
    segs = [
        {"start": 0, "end": 10, "score": 0.5},
        {"start": 11, "end": 25, "score": 0.6},  # gap=1s
    ]
    # merge_gap=2.0, no max_duration -> should merge even though duration is 25s
    merged = merge_segments(segs, merge_gap=2.0, max_duration=None)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 25


def test_merge_segments_at_video_boundaries():
    """Test segments at start/end of video (clamping handled elsewhere)."""
    segs = [
        {"start": 0, "end": 2, "score": 0.5},
        {"start": 28, "end": 30, "score": 0.6},  # near end of 30s video
    ]
    # Large gap, should not merge
    merged = merge_segments(segs, merge_gap=2.0, max_duration=10.0)
    assert len(merged) == 2


def test_merge_empty_list():
    """Test merging empty segment list."""
    merged = merge_segments([], merge_gap=2.0, max_duration=10.0)
    assert merged == []


def test_merge_single_segment():
    """Test merging a single segment."""
    segs = [{"start": 5, "end": 10, "score": 0.8}]
    merged = merge_segments(segs, merge_gap=2.0, max_duration=10.0)
    assert len(merged) == 1
    assert merged[0]["start"] == 5
    assert merged[0]["end"] == 10


# ============================================================================
# Original Tests (preserved)
# ============================================================================


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
