"""Tests for Pydantic models and validation."""

import pytest
from pydantic import ValidationError
from content_ai.models import (
    ContentAIConfig,
    DetectionConfig,
    OutputConfig,
    Segment,
    DetectionEvent,
)


def test_detection_config_valid():
    """Test creating valid DetectionConfig."""
    config = DetectionConfig(rms_threshold=0.15, min_event_duration_s=0.5)
    assert config.rms_threshold == 0.15
    assert config.min_event_duration_s == 0.5


def test_detection_config_invalid_rms_threshold():
    """Test that invalid RMS threshold raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        DetectionConfig(rms_threshold=1.5)  # > 1.0
    assert "rms_threshold" in str(exc_info.value)


def test_detection_config_negative_rms_threshold():
    """Test that negative RMS threshold raises ValidationError."""
    with pytest.raises(ValidationError):
        DetectionConfig(rms_threshold=-0.1)


def test_output_config_valid():
    """Test creating valid OutputConfig."""
    config = OutputConfig(max_duration_s=120, max_segments=20, order="score")
    assert config.max_duration_s == 120
    assert config.max_segments == 20
    assert config.order == "score"


def test_output_config_invalid_order():
    """Test that invalid order value raises ValidationError."""
    with pytest.raises(ValidationError):
        OutputConfig(order="invalid_order")


def test_content_ai_config_from_dict():
    """Test creating ContentAIConfig from dict."""
    data = {
        "detection": {"rms_threshold": 0.2},
        "processing": {"merge_gap_s": 3.0},
        "output": {"max_duration_s": 60}
    }
    config = ContentAIConfig.from_dict(data)
    assert config.detection.rms_threshold == 0.2
    assert config.processing.merge_gap_s == 3.0
    assert config.output.max_duration_s == 60


def test_content_ai_config_merge_cli_overrides():
    """Test merging CLI overrides into config."""
    config = ContentAIConfig()
    cli_args = {"rms_threshold": 0.3, "max_duration": 100}
    new_config = config.merge_cli_overrides(cli_args)

    assert new_config.detection.rms_threshold == 0.3
    assert new_config.output.max_duration_s == 100
    # Original config unchanged
    assert config.detection.rms_threshold == 0.1


def test_segment_valid():
    """Test creating valid Segment."""
    seg = Segment(start=1.0, end=5.0, score=0.8)
    assert seg.start == 1.0
    assert seg.end == 5.0
    assert seg.score == 0.8
    assert seg.duration == 4.0


def test_segment_end_before_start_invalid():
    """Test that segment with end < start raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Segment(start=5.0, end=3.0)
    assert "end" in str(exc_info.value).lower()


def test_segment_end_equals_start_invalid():
    """Test that segment with end == start raises ValidationError."""
    with pytest.raises(ValidationError):
        Segment(start=5.0, end=5.0)


def test_segment_negative_start_invalid():
    """Test that negative start time raises ValidationError."""
    with pytest.raises(ValidationError):
        Segment(start=-1.0, end=5.0)


def test_segment_invalid_score():
    """Test that score outside [0, 1] raises ValidationError."""
    with pytest.raises(ValidationError):
        Segment(start=1.0, end=5.0, score=1.5)


def test_segment_no_score_optional():
    """Test that score is optional."""
    seg = Segment(start=1.0, end=5.0)
    assert seg.score is None


def test_detection_event_valid():
    """Test creating valid DetectionEvent."""
    event = DetectionEvent(timestamp=10.5, rms_energy=0.75, score=0.9)
    assert event.timestamp == 10.5
    assert event.rms_energy == 0.75
    assert event.score == 0.9


def test_detection_event_negative_timestamp_invalid():
    """Test that negative timestamp raises ValidationError."""
    with pytest.raises(ValidationError):
        DetectionEvent(timestamp=-1.0, rms_energy=0.5)


def test_detection_event_negative_energy_invalid():
    """Test that negative energy raises ValidationError."""
    with pytest.raises(ValidationError):
        DetectionEvent(timestamp=10.0, rms_energy=-0.1)
