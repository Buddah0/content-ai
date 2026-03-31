from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from content_ai import detector


@pytest.fixture
def mock_librosa():
    with patch("content_ai.detector.librosa") as mock:
        yield mock


@pytest.fixture
def mock_video_clip():
    with patch("content_ai.detector.VideoFileClip") as mock:
        context_clip = mock.return_value.__enter__.return_value
        context_clip.audio = MagicMock()
        context_clip.duration = 10.0

        direct_clip = mock.return_value
        direct_clip.duration = 10.0
        direct_clip.subclip.return_value.iter_frames.return_value = []

        yield direct_clip


def test_adaptive_threshold(mock_librosa, mock_video_clip):
    # Setup mock audio data
    # 100 samples
    y = np.random.rand(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)

    # Mock HPSS to return same signal for simplicity
    mock_librosa.effects.hpss.return_value = (y, y)

    # Mock RMS: mostly 0.05, one peak at 0.5
    rms_vals = np.ones(100) * 0.05
    rms_vals[50] = 0.5  # The peak

    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = np.linspace(0, 10, 100)

    config = {"detection": {"adaptive_threshold": True, "sensitivity": 2.0, "rms_threshold": 0.1}}

    # Mean ~0.0545, Std ~0.045
    # Thresh = 0.0545 + 2*0.045 = ~0.1445
    # Peak (0.5) should be detected. Background (0.05) should not.

    segments = detector.detect_hype("dummy.mp4", config)

    assert len(segments) >= 1
    # Check that we found the peak around index 50 (time ~5.0s)
    # The actual integration might merge adjacent, but we have 1 peak.

    # Verify logical correctness of threshold usage
    # If we set sensitivity HUGE, we should find nothing
    config["detection"]["sensitivity"] = 100.0
    segments_strict = detector.detect_hype("dummy.mp4", config)
    assert len(segments_strict) == 0


def test_event_lookback(mock_librosa, mock_video_clip):
    # Setup mock audio
    y = np.zeros(100)
    sr = 22050  # Realistic sample rate
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    # Mock RMS: Background noise with a clear valley before event
    # This exercises the smart lookback: it should find the valley
    rms_vals = np.ones(20) * 0.05  # Background noise
    rms_vals[7] = 0.01             # Quiet valley at t=7
    rms_vals[8] = 0.02             # Still quiet
    rms_vals[9] = 0.15             # Rising
    rms_vals[10] = 0.5             # Event peak
    rms_vals[11] = 0.3             # Decaying

    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    # Times 0..19s
    times = np.arange(20, dtype=float)
    mock_librosa.times_like.return_value = times

    # Mock librosa.frames_to_time for smart_lookback
    mock_librosa.frames_to_time.side_effect = lambda indices, sr, hop_length: np.array(
        [times[i] if i < len(times) else times[-1] for i in indices]
    )

    config = {
        "detection": {"adaptive_threshold": False, "rms_threshold": 0.1, "event_lookback_s": 5.0}
    }

    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) >= 1
    # Event starts at t=9, so 5s lookback scans [4, 9].
    # The minimum in that window is at t=7.
    assert segments[0]["start"] == 7.0
    assert segments[0]["end"] == 12.0  # Ends after index 11 -> t=12 (first non-hype sample)

    # Setup mock audio
    y = np.zeros(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    # Mock RMS: all 0.05
    rms_vals = np.ones(100) * 0.05
    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = np.linspace(0, 10, 100)

    config = {"detection": {"adaptive_threshold": False, "rms_threshold": 0.1}}

    # Should find nothing as 0.05 < 0.1
    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) == 0

    # Lower threshold
    config["detection"]["rms_threshold"] = 0.01
    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) > 0


def test_flash_scan_window_ends_at_event_start(mock_librosa, mock_video_clip):
    y = np.zeros(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    rms_vals = np.ones(20) * 0.05
    rms_vals[7] = 0.01
    rms_vals[8] = 0.02
    rms_vals[9] = 0.15
    rms_vals[10] = 0.5
    rms_vals[11] = 0.3

    times = np.arange(20, dtype=float)
    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = times
    mock_librosa.frames_to_time.side_effect = lambda indices, sr, hop_length: np.array(
        [times[i] if i < len(times) else times[-1] for i in indices]
    )

    config = {
        "detection": {"adaptive_threshold": False, "rms_threshold": 0.1, "event_lookback_s": 5.0}
    }

    segments = detector.detect_hype("dummy.mp4", config)

    assert len(segments) >= 1
    mock_video_clip.subclip.assert_called_once_with(7.0, 9.0)
