"""Verification tests for deterministic output guarantee.

These tests prove that the content-ai pipeline produces identical
output given identical inputs and configuration.
"""

import random

import pytest

from content_ai.hashing import deterministic_segment_id
from content_ai.segments import clamp_segments, merge_segments, pad_segments


class TestDeterministicSegmentIds:
    """Verify content-addressable segment IDs."""

    def test_same_inputs_same_id(self):
        """Same content properties always produce the same ID."""
        id1 = deterministic_segment_id("/videos/a.mp4", 10.5, 15.3, 0.85)
        id2 = deterministic_segment_id("/videos/a.mp4", 10.5, 15.3, 0.85)
        assert id1 == id2

    def test_different_inputs_different_id(self):
        """Different content properties produce different IDs."""
        id1 = deterministic_segment_id("/videos/a.mp4", 10.5, 15.3, 0.85)
        id2 = deterministic_segment_id("/videos/a.mp4", 10.5, 15.3, 0.86)
        assert id1 != id2

    def test_id_format(self):
        """IDs are 12-char hex strings."""
        seg_id = deterministic_segment_id("/videos/a.mp4", 1.0, 2.0, 0.5)
        assert len(seg_id) == 12
        assert all(c in "0123456789abcdef" for c in seg_id)

    def test_path_sensitivity(self):
        """Different source paths produce different IDs."""
        id1 = deterministic_segment_id("/videos/a.mp4", 1.0, 2.0, 0.5)
        id2 = deterministic_segment_id("/videos/b.mp4", 1.0, 2.0, 0.5)
        assert id1 != id2

    def test_float_precision_stability(self):
        """IDs are stable across float representation edge cases."""
        # 0.1 + 0.2 != 0.3 in IEEE 754, but :.6f formatting normalizes it
        id1 = deterministic_segment_id("/v.mp4", 0.1 + 0.2, 1.0, 0.5)
        id2 = deterministic_segment_id("/v.mp4", 0.3, 1.0, 0.5)
        assert id1 == id2


class TestPipelineDeterminism:
    """Verify that the full segment processing pipeline is deterministic."""

    SYNTHETIC_RAW_SEGMENTS = [
        {"start": 2.0, "end": 3.0, "score": 0.8, "video_duration": 30.0},
        {"start": 4.5, "end": 5.5, "score": 0.6, "video_duration": 30.0},
        {"start": 10.0, "end": 11.0, "score": 0.9, "video_duration": 30.0},
        {"start": 15.0, "end": 16.5, "score": 0.7, "video_duration": 30.0},
        {"start": 20.0, "end": 21.0, "score": 0.5, "video_duration": 30.0},
        {"start": 21.5, "end": 22.5, "score": 0.6, "video_duration": 30.0},
    ]

    def _run_segment_pipeline(self, raw_segments):
        """Run the segment processing pipeline (pad -> clamp -> merge -> id)."""
        padded = pad_segments(raw_segments, padding=1.0)
        clamped = clamp_segments(padded, 0.0, 30.0)
        merged = merge_segments(clamped, merge_gap=2.0, max_duration=10.0)

        source_path = "/test/video.mp4"
        for s in merged:
            s["source_path"] = source_path
            s["id"] = deterministic_segment_id(
                source_path, s["start"], s["end"], s.get("score", 0)
            )
        return merged

    def test_identical_runs_produce_identical_output(self):
        """Running the pipeline twice on identical input produces identical output."""
        run1 = self._run_segment_pipeline(self.SYNTHETIC_RAW_SEGMENTS)
        run2 = self._run_segment_pipeline(self.SYNTHETIC_RAW_SEGMENTS)

        assert len(run1) == len(run2)
        for seg1, seg2 in zip(run1, run2):
            assert seg1["id"] == seg2["id"]
            assert seg1["start"] == seg2["start"]
            assert seg1["end"] == seg2["end"]
            assert seg1.get("score") == seg2.get("score")
            assert seg1["source_path"] == seg2["source_path"]

    def test_segment_ids_are_unique_within_run(self):
        """All segment IDs within a single run are unique."""
        segments = self._run_segment_pipeline(self.SYNTHETIC_RAW_SEGMENTS)
        ids = [s["id"] for s in segments]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_ordering_is_stable(self):
        """Segment ordering is deterministic across runs."""
        run1 = self._run_segment_pipeline(self.SYNTHETIC_RAW_SEGMENTS)
        run2 = self._run_segment_pipeline(self.SYNTHETIC_RAW_SEGMENTS)

        starts1 = [s["start"] for s in run1]
        starts2 = [s["start"] for s in run2]
        assert starts1 == starts2

    def test_shuffled_input_same_output(self):
        """Pipeline produces same output regardless of input order."""
        shuffled = self.SYNTHETIC_RAW_SEGMENTS.copy()
        random.seed(99)
        random.shuffle(shuffled)

        normal_result = self._run_segment_pipeline(self.SYNTHETIC_RAW_SEGMENTS)
        shuffled_result = self._run_segment_pipeline(shuffled)

        normal_ids = sorted(s["id"] for s in normal_result)
        shuffled_ids = sorted(s["id"] for s in shuffled_result)
        assert normal_ids == shuffled_ids
