from unittest.mock import MagicMock, patch

import pytest

from content_ai.models import ContentAIConfig
from content_ai.renderer import render_segment_to_file, verify_output_integrity


# Mock config
@pytest.fixture
def mock_config():
    return {"output": {"output_format": "webm", "keep_temp": False}, "rendering": {}}


def test_config_output_format_default():
    """Test default output format is mp4."""
    config = ContentAIConfig()
    assert config.output.output_format == "mp4"


def test_config_output_format_webm():
    """Test setting output format to webm."""
    config_data = {"output": {"output_format": "webm"}}
    config = ContentAIConfig.from_dict(config_data)
    assert config.output.output_format == "webm"


def test_renderer_webm_contract_legacy(tmp_path):
    """Test render_segment_to_file passes correct arguments for WebM."""
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.webm"

    # Create dummy source file (empty is fine as we mock VideoFileClip)
    source.touch()

    with patch("content_ai.renderer.VideoFileClip") as mock_clip_cls:
        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        mock_subclip = MagicMock()
        mock_clip.subclip.return_value = mock_subclip
        mock_clip_cls.return_value.__enter__.return_value = mock_clip

        render_segment_to_file(str(source), 0.0, 5.0, str(output), output_format="webm")

        # Verify write_videofile called with correct codec settings
        mock_subclip.write_videofile.assert_called_once()
        call_kwargs = mock_subclip.write_videofile.call_args[1]

        assert call_kwargs["codec"] == "libvpx-vp9"
        assert call_kwargs["audio_codec"] == "libopus"
        assert call_kwargs["ffmpeg_params"] is not None
        assert "-speed" in call_kwargs["ffmpeg_params"]
        assert call_kwargs.get("audio_bitrate") == "96k"


def test_renderer_mp4_contract_legacy(tmp_path):
    """Test render_segment_to_file passes correct arguments for MP4."""
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    source.touch()

    with patch("content_ai.renderer.VideoFileClip") as mock_clip_cls:
        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        mock_subclip = MagicMock()
        mock_clip.subclip.return_value = mock_subclip
        mock_clip_cls.return_value.__enter__.return_value = mock_clip

        render_segment_to_file(str(source), 0.0, 5.0, str(output), output_format="mp4")

        mock_subclip.write_videofile.assert_called_once()
        call_kwargs = mock_subclip.write_videofile.call_args[1]

        assert call_kwargs["codec"] == "libx264"
        assert call_kwargs["audio_codec"] == "aac"
        assert call_kwargs["preset"] == "ultrafast"


def test_verify_output_integrity_success(tmp_path):
    """Test integrity check passes for valid file."""
    fake_file = tmp_path / "valid.webm"
    fake_file.write_bytes(b"some content")

    with patch("content_ai.renderer.probe_video") as mock_probe:
        # Mock metadata
        mock_meta = MagicMock()
        mock_meta.codec_name = "vp9"
        mock_meta.audio_codec = "opus"
        mock_meta.duration = 5.0
        mock_probe.return_value = mock_meta

        metrics = verify_output_integrity(str(fake_file), expected_format="webm")

        assert metrics["output.format"] == "webm"
        assert metrics["output.size_bytes"] > 0
        assert "output.sha256" in metrics


def test_verify_output_integrity_empty(tmp_path):
    """Test integrity check fails for empty file."""
    empty_file = tmp_path / "empty.webm"
    empty_file.touch()

    with pytest.raises(ValueError, match="is empty"):
        verify_output_integrity(str(empty_file))


def test_verify_output_integrity_missing(tmp_path):
    """Test integrity check fails for missing file."""
    missing = tmp_path / "missing.webm"

    with pytest.raises(FileNotFoundError):
        verify_output_integrity(str(missing))
