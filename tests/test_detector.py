
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from content_ai import detector

@pytest.fixture
def mock_librosa():
    with patch("content_ai.detector.librosa") as mock:
        yield mock

@pytest.fixture
def mock_video_clip():
    with patch("content_ai.detector.VideoFileClip") as mock:
        mock_instance = mock.return_value.__enter__.return_value
        mock_instance.audio = MagicMock()
        mock_instance.duration = 10.0
        yield mock_instance

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
    rms_vals[50] = 0.5 # The peak
    
    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = np.linspace(0, 10, 100)
    
    config = {
        "detection": {
            "adaptive_threshold": True,
            "sensitivity": 2.0,
            "rms_threshold": 0.1
        }
    }
    
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
    sr = 1 # 1 sample per second for easy math
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)
    
    # Mock RMS: Event at t=10s (index 10)
    rms_vals = np.zeros(20)
    rms_vals[10] = 0.5 
    
    detector.librosa.feature.rms.return_value = np.array([rms_vals])
    # Times 0..19s
    detector.librosa.times_like.return_value = np.arange(20, dtype=float)
    
    config = {
        "detection": {
            "adaptive_threshold": False,
            "rms_threshold": 0.1,
            "event_lookback_s": 3.0
        }
    }
    
    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) == 1
    # Event is at t=10. Lookback is 3. Start should be 7.
    assert segments[0]["start"] == 7.0
    # Event is at t=10. Lookback is 3. Start should be 7.
    assert segments[0]["start"] == 7.0
    assert segments[0]["end"] == 11.0 # Ends at t=11 (first non-hype sample)


    # Setup mock audio
    y = np.zeros(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    # Mock RMS: all 0.05
    rms_vals = np.ones(100) * 0.05
    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = np.linspace(0, 10, 100)
    
    config = {
        "detection": {
            "adaptive_threshold": False,
            "rms_threshold": 0.1
        }
    }
    
    # Should find nothing as 0.05 < 0.1
    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) == 0
    
    # Lower threshold
    config["detection"]["rms_threshold"] = 0.01
    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) > 0

