"""Unit tests for renderer with VFR detection and normalization."""

import json
import subprocess
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from content_ai.renderer import (
    VideoMetadata,
    probe_video,
    should_use_fast_path,
    validate_segment_compatibility,
    render_segment_with_runner,
    concat_with_runner
)


class TestVideoMetadata:
    """Test VideoMetadata dataclass."""

    def test_video_metadata_creation(self):
        """Test creating VideoMetadata instance."""
        metadata = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="60/1",
            avg_frame_rate="60/1",
            is_vfr=False,
            fps_numeric=60.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.5,
            bitrate=5000000
        )

        assert metadata.codec_name == "h264"
        assert metadata.fps_numeric == 60.0
        assert metadata.is_vfr is False


class TestProbeVideo:
    """Test video probing with ffprobe."""

    def create_mock_ffprobe_output(
        self,
        codec="h264",
        profile="High",
        r_frame_rate="60/1",
        avg_frame_rate="60/1",
        pix_fmt="yuv420p",
        width=1920,
        height=1080,
        audio_codec="aac",
        sample_rate="48000",
        channels=2,
        duration="120.5",
        bitrate="5000000"
    ):
        """Create mock ffprobe JSON output."""
        return json.dumps({
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": codec,
                    "profile": profile,
                    "level": 41,
                    "pix_fmt": pix_fmt,
                    "width": width,
                    "height": height,
                    "r_frame_rate": r_frame_rate,
                    "avg_frame_rate": avg_frame_rate
                },
                {
                    "codec_type": "audio",
                    "codec_name": audio_codec,
                    "sample_rate": sample_rate,
                    "channels": channels
                }
            ],
            "format": {
                "duration": duration,
                "bit_rate": bitrate
            }
        })

    @patch('subprocess.run')
    @patch('content_ai.renderer.get_ffmpeg_cmd')
    def test_probe_cfr_video(self, mock_get_ffmpeg, mock_run):
        """Test probing a CFR (Constant Frame Rate) video."""
        mock_get_ffmpeg.return_value = "/usr/bin/ffmpeg"

        # Mock ffprobe output for CFR video
        mock_result = MagicMock()
        mock_result.stdout = self.create_mock_ffprobe_output(
            r_frame_rate="60/1",
            avg_frame_rate="60/1"  # Same = CFR
        )
        mock_run.return_value = mock_result

        metadata = probe_video("test.mp4")

        assert metadata.codec_name == "h264"
        assert metadata.r_frame_rate == "60/1"
        assert metadata.avg_frame_rate == "60/1"
        assert metadata.is_vfr is False
        assert metadata.fps_numeric == pytest.approx(60.0, rel=0.01)

    @patch('subprocess.run')
    @patch('content_ai.renderer.get_ffmpeg_cmd')
    def test_probe_vfr_video(self, mock_get_ffmpeg, mock_run):
        """Test probing a VFR (Variable Frame Rate) video."""
        mock_get_ffmpeg.return_value = "/usr/bin/ffmpeg"

        # Mock ffprobe output for VFR video
        # r_frame_rate = 30, avg_frame_rate = ~30.6 (2% difference)
        # This simulates a VFR source where actual frame delivery differs from declared rate
        mock_result = MagicMock()
        mock_result.stdout = self.create_mock_ffprobe_output(
            r_frame_rate="30/1",
            avg_frame_rate="306/10"  # = 30.6 fps (2% higher than declared 30)
        )
        mock_run.return_value = mock_result

        metadata = probe_video("test_vfr.mp4", frame_rate_tolerance=0.01)

        assert metadata.r_frame_rate == "30/1"
        assert metadata.avg_frame_rate == "306/10"
        assert metadata.is_vfr is True  # Difference > 1% (2% in this case)
        assert metadata.fps_numeric == pytest.approx(30.6, rel=0.01)

    @patch('subprocess.run')
    @patch('content_ai.renderer.get_ffmpeg_cmd')
    def test_probe_video_no_audio(self, mock_get_ffmpeg, mock_run):
        """Test probing a video without audio stream."""
        mock_get_ffmpeg.return_value = "/usr/bin/ffmpeg"

        # Mock ffprobe output for video-only file
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "profile": "High",
                    "level": 41,
                    "pix_fmt": "yuv420p",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "avg_frame_rate": "30/1"
                }
            ],
            "format": {
                "duration": "60.0"
            }
        })
        mock_run.return_value = mock_result

        metadata = probe_video("test_no_audio.mp4")

        assert metadata.codec_name == "h264"
        assert metadata.audio_codec is None
        assert metadata.audio_sample_rate is None
        assert metadata.audio_channels is None

    @patch('subprocess.run')
    @patch('content_ai.renderer.get_ffmpeg_cmd')
    def test_probe_video_ffprobe_failure(self, mock_get_ffmpeg, mock_run):
        """Test handling ffprobe failure."""
        mock_get_ffmpeg.return_value = "/usr/bin/ffmpeg"

        # Mock ffprobe failure
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffprobe"],
            stderr=b"No such file or directory"
        )

        with pytest.raises(RuntimeError, match="ffprobe failed"):
            probe_video("nonexistent.mp4")

    @patch('subprocess.run')
    @patch('content_ai.renderer.get_ffmpeg_cmd')
    def test_probe_video_no_video_stream(self, mock_get_ffmpeg, mock_run):
        """Test handling audio-only file (no video stream)."""
        mock_get_ffmpeg.return_value = "/usr/bin/ffmpeg"

        # Mock ffprobe output for audio-only file
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2
                }
            ],
            "format": {
                "duration": "60.0"
            }
        })
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError, match="No video stream found"):
            probe_video("audio_only.m4a")

    @patch('subprocess.run')
    @patch('content_ai.renderer.get_ffmpeg_cmd')
    def test_probe_video_timeout(self, mock_get_ffmpeg, mock_run):
        """Test handling ffprobe timeout."""
        mock_get_ffmpeg.return_value = "/usr/bin/ffmpeg"

        # Mock ffprobe timeout
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["ffprobe"],
            timeout=30
        )

        with pytest.raises(RuntimeError, match="timed out"):
            probe_video("large_file.mp4")


class TestFastPathDecision:
    """Test fast path decision logic."""

    def test_fast_path_enabled_for_cfr(self):
        """Test fast path enabled for CFR video."""
        metadata = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="60/1",
            avg_frame_rate="60/1",
            is_vfr=False,  # CFR
            fps_numeric=60.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Fast path should be enabled for CFR
        assert should_use_fast_path(
            metadata,
            normalize_to_contract=False,
            force_cfr=True,
            fast_path_enabled=True
        ) is True

    def test_fast_path_disabled_for_vfr(self):
        """Test fast path disabled for VFR video when force_cfr=True."""
        metadata = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="60/1",
            avg_frame_rate="1349280/22481",
            is_vfr=True,  # VFR
            fps_numeric=60.02,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Fast path should be disabled for VFR when force_cfr=True
        assert should_use_fast_path(
            metadata,
            normalize_to_contract=False,
            force_cfr=True,
            fast_path_enabled=True
        ) is False

    def test_fast_path_allowed_for_vfr_when_cfr_not_forced(self):
        """Test fast path allowed for VFR when force_cfr=False."""
        metadata = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="60/1",
            avg_frame_rate="1349280/22481",
            is_vfr=True,  # VFR
            fps_numeric=60.02,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Fast path allowed when force_cfr=False
        assert should_use_fast_path(
            metadata,
            normalize_to_contract=False,
            force_cfr=False,
            fast_path_enabled=True
        ) is True

    def test_fast_path_disabled_when_normalization_forced(self):
        """Test fast path disabled when normalize_to_contract=True."""
        metadata = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="60/1",
            avg_frame_rate="60/1",
            is_vfr=False,
            fps_numeric=60.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Fast path disabled when normalization forced
        assert should_use_fast_path(
            metadata,
            normalize_to_contract=True,
            force_cfr=True,
            fast_path_enabled=True
        ) is False

    def test_fast_path_disabled_globally(self):
        """Test fast path disabled when fast_path_enabled=False."""
        metadata = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="60/1",
            avg_frame_rate="60/1",
            is_vfr=False,
            fps_numeric=60.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Fast path disabled globally
        assert should_use_fast_path(
            metadata,
            normalize_to_contract=False,
            force_cfr=True,
            fast_path_enabled=False
        ) is False


class TestSegmentCompatibility:
    """Test segment compatibility validation."""

    @patch('content_ai.renderer.probe_video')
    def test_compatible_segments(self, mock_probe):
        """Test validation with compatible segments."""
        # All segments have identical specs
        mock_probe.return_value = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="30/1",
            avg_frame_rate="30/1",
            is_vfr=False,
            fps_numeric=30.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=10.0,
            bitrate=5000000
        )

        segments = ["clip_000.mp4", "clip_001.mp4", "clip_002.mp4"]
        assert validate_segment_compatibility(segments) is True

    @patch('content_ai.renderer.probe_video')
    def test_incompatible_codecs(self, mock_probe):
        """Test validation with incompatible codecs."""
        # First segment: h264
        # Second segment: h265
        mock_probe.side_effect = [
            VideoMetadata(
                codec_name="h264",
                profile="High",
                level=41,
                pixel_format="yuv420p",
                width=1920,
                height=1080,
                r_frame_rate="30/1",
                avg_frame_rate="30/1",
                is_vfr=False,
                fps_numeric=30.0,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration=10.0,
                bitrate=5000000
            ),
            VideoMetadata(
                codec_name="hevc",  # Different codec
                profile="Main",
                level=41,
                pixel_format="yuv420p",
                width=1920,
                height=1080,
                r_frame_rate="30/1",
                avg_frame_rate="30/1",
                is_vfr=False,
                fps_numeric=30.0,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration=10.0,
                bitrate=5000000
            )
        ]

        segments = ["clip_000.mp4", "clip_001.mp4"]
        assert validate_segment_compatibility(segments) is False

    @patch('content_ai.renderer.probe_video')
    def test_incompatible_fps(self, mock_probe):
        """Test validation with incompatible frame rates."""
        # First segment: 30fps
        # Second segment: 60fps
        mock_probe.side_effect = [
            VideoMetadata(
                codec_name="h264",
                profile="High",
                level=41,
                pixel_format="yuv420p",
                width=1920,
                height=1080,
                r_frame_rate="30/1",
                avg_frame_rate="30/1",
                is_vfr=False,
                fps_numeric=30.0,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration=10.0,
                bitrate=5000000
            ),
            VideoMetadata(
                codec_name="h264",
                profile="High",
                level=41,
                pixel_format="yuv420p",
                width=1920,
                height=1080,
                r_frame_rate="60/1",
                avg_frame_rate="60/1",
                is_vfr=False,
                fps_numeric=60.0,  # Different FPS
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration=10.0,
                bitrate=5000000
            )
        ]

        segments = ["clip_000.mp4", "clip_001.mp4"]
        assert validate_segment_compatibility(segments) is False

    @patch('content_ai.renderer.probe_video')
    def test_vfr_detected_in_segments(self, mock_probe):
        """Test validation rejects VFR segments."""
        # Second segment is VFR
        mock_probe.side_effect = [
            VideoMetadata(
                codec_name="h264",
                profile="High",
                level=41,
                pixel_format="yuv420p",
                width=1920,
                height=1080,
                r_frame_rate="60/1",
                avg_frame_rate="60/1",
                is_vfr=False,  # CFR
                fps_numeric=60.0,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration=10.0,
                bitrate=5000000
            ),
            VideoMetadata(
                codec_name="h264",
                profile="High",
                level=41,
                pixel_format="yuv420p",
                width=1920,
                height=1080,
                r_frame_rate="60/1",
                avg_frame_rate="1349280/22481",
                is_vfr=True,  # VFR
                fps_numeric=60.02,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration=10.0,
                bitrate=5000000
            )
        ]

        segments = ["clip_000.mp4", "clip_001.mp4"]
        assert validate_segment_compatibility(segments) is False

    def test_empty_segment_list(self):
        """Test validation with empty segment list."""
        assert validate_segment_compatibility([]) is True


# ============================================================================
# PR #3 Integration Tests - FfmpegRunner Integration
# ============================================================================


class TestRenderSegmentWithRunner:
    """Test render_segment_with_runner function."""

    @patch('content_ai.renderer.probe_video')
    @patch('content_ai.ffmpeg_runner.FfmpegRunner')
    def test_render_with_runner_cfr_fast_path(self, mock_runner_cls, mock_probe):
        """Test rendering CFR video uses fast path (stream copy)."""
        from content_ai.renderer import render_segment_with_runner
        from content_ai.models import RenderingConfig
        from content_ai.ffmpeg_runner import FfmpegResult

        # Mock probe returns CFR video
        mock_probe.return_value = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="30/1",
            avg_frame_rate="30/1",
            is_vfr=False,
            fps_numeric=30.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Mock FfmpegRunner
        mock_runner = MagicMock()
        mock_runner.extract_segment.return_value = FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=1.0
        )
        mock_runner_cls.return_value = mock_runner

        # Render with fast path enabled
        config = RenderingConfig(
            fast_path_enabled=True,
            normalize_to_contract=False
        )
        result = render_segment_with_runner(
            "input.mp4", 10.0, 20.0, "output.mp4",
            rendering_config=config
        )

        assert result.success is True
        # Verify stream copy was used (fast path)
        mock_runner.extract_segment.assert_called_once()
        call_args = mock_runner.extract_segment.call_args
        assert call_args.kwargs['codec'] == 'copy'
        assert call_args.kwargs['audio_codec'] == 'copy'

    @patch('content_ai.renderer.probe_video')
    @patch('content_ai.ffmpeg_runner.FfmpegRunner')
    def test_render_with_runner_vfr_reencode(self, mock_runner_cls, mock_probe):
        """Test rendering VFR video triggers re-encode."""
        from content_ai.renderer import render_segment_with_runner
        from content_ai.models import RenderingConfig
        from content_ai.ffmpeg_runner import FfmpegResult

        # Mock probe returns VFR video
        mock_probe.return_value = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="30/1",
            avg_frame_rate="306/10",  # VFR: 2% difference
            is_vfr=True,
            fps_numeric=30.6,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Mock FfmpegRunner
        mock_runner = MagicMock()
        mock_runner.extract_segment.return_value = FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=5.0
        )
        mock_runner_cls.return_value = mock_runner

        # Render with force_cfr enabled (default)
        config = RenderingConfig(
            fast_path_enabled=True,
            force_cfr=True,  # Should trigger re-encode for VFR
            normalize_to_contract=False
        )
        result = render_segment_with_runner(
            "input.mp4", 10.0, 20.0, "output.mp4",
            rendering_config=config
        )

        assert result.success is True
        # Verify re-encode was used (not stream copy)
        mock_runner.extract_segment.assert_called_once()
        call_args = mock_runner.extract_segment.call_args
        assert call_args.kwargs['codec'] == 'libx264'  # Re-encode
        assert call_args.kwargs['target_fps'] == 30  # CFR enforcement

    @patch('content_ai.renderer.probe_video')
    @patch('content_ai.ffmpeg_runner.FfmpegRunner')
    def test_render_with_runner_forced_normalization(self, mock_runner_cls, mock_probe):
        """Test normalize_to_contract=True always re-encodes."""
        from content_ai.renderer import render_segment_with_runner
        from content_ai.models import RenderingConfig
        from content_ai.ffmpeg_runner import FfmpegResult

        # Mock probe returns perfect CFR video
        mock_probe.return_value = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="30/1",
            avg_frame_rate="30/1",
            is_vfr=False,
            fps_numeric=30.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Mock FfmpegRunner
        mock_runner = MagicMock()
        mock_runner.extract_segment.return_value = FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=5.0
        )
        mock_runner_cls.return_value = mock_runner

        # Force normalization even for CFR video
        config = RenderingConfig(
            normalize_to_contract=True,  # Force re-encode
            fast_path_enabled=True
        )
        result = render_segment_with_runner(
            "input.mp4", 10.0, 20.0, "output.mp4",
            rendering_config=config
        )

        assert result.success is True
        # Verify re-encode was used despite CFR source
        mock_runner.extract_segment.assert_called_once()
        call_args = mock_runner.extract_segment.call_args
        assert call_args.kwargs['codec'] == 'libx264'

    @patch('content_ai.renderer.probe_video')
    @patch('content_ai.ffmpeg_runner.FfmpegRunner')
    def test_render_with_runner_uses_default_config(self, mock_runner_cls, mock_probe):
        """Test render uses default RenderingConfig when not provided."""
        from content_ai.renderer import render_segment_with_runner
        from content_ai.ffmpeg_runner import FfmpegResult

        # Mock probe returns CFR video
        mock_probe.return_value = VideoMetadata(
            codec_name="h264",
            profile="High",
            level=41,
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            r_frame_rate="30/1",
            avg_frame_rate="30/1",
            is_vfr=False,
            fps_numeric=30.0,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            duration=120.0,
            bitrate=5000000
        )

        # Mock FfmpegRunner
        mock_runner = MagicMock()
        mock_runner.extract_segment.return_value = FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=1.0
        )
        mock_runner_cls.return_value = mock_runner

        # Call without config - should use defaults
        result = render_segment_with_runner(
            "input.mp4", 10.0, 20.0, "output.mp4"
        )

        assert result.success is True
        # Verify FfmpegRunner was created with default timeout values
        mock_runner_cls.assert_called_once()
        call_args = mock_runner_cls.call_args
        assert call_args.kwargs['global_timeout_s'] == 1800  # Default
        assert call_args.kwargs['no_progress_timeout_s'] == 120  # Default


class TestConcatWithRunner:
    """Test concat_with_runner function."""

    @patch('content_ai.renderer.validate_segment_compatibility')
    @patch('content_ai.ffmpeg_runner.FfmpegRunner')
    def test_concat_with_validation(self, mock_runner_cls, mock_validate):
        """Test concat validates segments before concatenation."""
        from content_ai.renderer import concat_with_runner
        from content_ai.models import RenderingConfig
        from content_ai.ffmpeg_runner import FfmpegResult

        mock_validate.return_value = True

        # Mock FfmpegRunner
        mock_runner = MagicMock()
        mock_runner.concat_videos.return_value = FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=1.0
        )
        mock_runner_cls.return_value = mock_runner

        config = RenderingConfig(validate_before_concat=True)
        segments = ["clip_000.mp4", "clip_001.mp4"]
        result = concat_with_runner(segments, "output.mp4", rendering_config=config)

        assert result.success is True
        mock_validate.assert_called_once_with(segments, frame_rate_tolerance=0.01)
        mock_runner.concat_videos.assert_called_once_with(segments, "output.mp4")

    def test_concat_empty_segments(self):
        """Test concat with empty segment list returns success."""
        from content_ai.renderer import concat_with_runner

        result = concat_with_runner([], "output.mp4")

        assert result.success is True
        assert result.stderr == "No segments to concatenate"

    @patch('content_ai.renderer.validate_segment_compatibility')
    @patch('content_ai.ffmpeg_runner.FfmpegRunner')
    def test_concat_skips_validation_when_disabled(self, mock_runner_cls, mock_validate):
        """Test concat skips validation when validate_before_concat=False."""
        from content_ai.renderer import concat_with_runner
        from content_ai.models import RenderingConfig
        from content_ai.ffmpeg_runner import FfmpegResult

        # Mock FfmpegRunner
        mock_runner = MagicMock()
        mock_runner.concat_videos.return_value = FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=1.0
        )
        mock_runner_cls.return_value = mock_runner

        config = RenderingConfig(validate_before_concat=False)
        segments = ["clip_000.mp4", "clip_001.mp4"]
        result = concat_with_runner(segments, "output.mp4", rendering_config=config)

        assert result.success is True
        mock_validate.assert_not_called()


class TestWorkerIntegration:
    """Test worker.py integration with FfmpegRunner."""

    def test_process_video_job_signature(self):
        """Test process_video_job accepts use_ffmpeg_runner parameter."""
        from content_ai.queue.worker import process_video_job
        import inspect

        sig = inspect.signature(process_video_job)
        params = list(sig.parameters.keys())

        assert 'use_ffmpeg_runner' in params
        # Verify default is False for backward compatibility
        assert sig.parameters['use_ffmpeg_runner'].default is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
