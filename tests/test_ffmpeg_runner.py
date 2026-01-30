"""Unit tests for FFmpeg runner with process isolation and timeout enforcement."""

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from content_ai.ffmpeg_runner import FfmpegErrorType, FfmpegProgress, FfmpegResult, FfmpegRunner


class TestProgressParsing:
    """Test FFmpeg progress parsing from stderr."""

    def test_parse_out_time(self):
        """Test parsing out_time from FFmpeg progress output."""
        runner = FfmpegRunner()
        runner._progress = FfmpegProgress()

        # Simulate FFmpeg progress line
        mock_stderr = ["frame=  123\n", "fps=25.00\n", "out_time=00:00:05.50\n", "speed=2.5x\n"]

        # Mock the stderr stream
        runner._monitor_progress(iter(mock_stderr))

        # Verify parsed values
        assert runner._progress.current_time_s == pytest.approx(5.5, rel=0.01)
        assert runner._progress.frame == 123
        assert runner._progress.fps == pytest.approx(25.0, rel=0.01)
        assert runner._progress.speed == pytest.approx(2.5, rel=0.01)

    def test_parse_large_time(self):
        """Test parsing large time values (hours)."""
        runner = FfmpegRunner()
        runner._progress = FfmpegProgress()

        mock_stderr = ["out_time=01:23:45.67\n"]

        runner._monitor_progress(iter(mock_stderr))

        # 1h 23m 45.67s = 3600 + 1380 + 45.67 = 5025.67
        expected_time = 1 * 3600 + 23 * 60 + 45.67
        assert runner._progress.current_time_s == pytest.approx(expected_time, rel=0.01)

    def test_progress_callback_invoked(self):
        """Test that progress callback is invoked."""
        callback_invoked = []

        def progress_callback(progress: FfmpegProgress):
            callback_invoked.append(progress.current_time_s)

        runner = FfmpegRunner(progress_callback=progress_callback)
        runner._progress = FfmpegProgress()

        # Simulate multiple progress updates with time gaps
        mock_stderr = ["out_time=00:00:01.00\n", "out_time=00:00:02.00\n", "out_time=00:00:03.00\n"]

        # Patch time.time to control callback timing
        with patch("time.time") as mock_time:
            # First progress update at t=0
            mock_time.return_value = 0.0
            runner._monitor_progress(iter([mock_stderr[0]]))

            # Second update at t=2.5 (should trigger callback)
            mock_time.return_value = 2.5
            runner._monitor_progress(iter([mock_stderr[1]]))

        # Callback should have been invoked at least once
        assert len(callback_invoked) >= 1


class TestErrorClassification:
    """Test FFmpeg error classification for retry logic."""

    def test_classify_permanent_errors(self):
        """Test that permanent errors are classified correctly."""
        runner = FfmpegRunner()

        # Test various permanent error patterns
        permanent_cases = [
            "input.mp4: No such file or directory",
            "Invalid data found when processing input",
            "Permission denied",
            "Unsupported codec for output stream",
            "moov atom not found",
        ]

        for stderr in permanent_cases:
            error_type = runner._classify_error(stderr)
            assert error_type == FfmpegErrorType.PERMANENT, f"Expected PERMANENT for: {stderr}"

    def test_classify_transient_errors(self):
        """Test that transient errors are classified correctly."""
        runner = FfmpegRunner()

        # Test various transient error patterns
        transient_cases = [
            "I/O error reading input",
            "Connection refused",
            "Connection timeout",
            "Resource temporarily unavailable",
            "Disk full",
        ]

        for stderr in transient_cases:
            error_type = runner._classify_error(stderr)
            assert error_type == FfmpegErrorType.TRANSIENT, f"Expected TRANSIENT for: {stderr}"

    def test_classify_unknown_as_transient(self):
        """Test that unknown errors default to transient."""
        runner = FfmpegRunner()

        stderr = "Some unknown error message"
        error_type = runner._classify_error(stderr)

        # Unknown errors should be treated as transient (retry)
        assert error_type == FfmpegErrorType.TRANSIENT


class TestCommandGeneration:
    """Test FFmpeg command generation."""

    def test_extract_segment_basic_command(self):
        """Test basic segment extraction command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir)

            # Mock _run_ffmpeg to capture command
            captured_cmd = []

            def mock_run_ffmpeg(cmd, expected_duration=None):
                captured_cmd.append(cmd)
                return FfmpegResult(
                    success=True, returncode=0, stdout="", stderr="", duration_s=1.0
                )

            runner._run_ffmpeg = mock_run_ffmpeg

            # Extract segment
            runner.extract_segment(
                source_path="input.mp4", start=10.0, end=20.0, output_path="output.mp4"
            )

            # Verify command structure
            assert len(captured_cmd) == 1
            cmd = captured_cmd[0]

            assert "-ss" in cmd
            assert "10.0" in cmd
            assert "-t" in cmd
            assert "10.0" in cmd  # duration = end - start
            assert "-i" in cmd
            assert "input.mp4" in cmd
            assert "output.mp4" in cmd

    def test_extract_segment_with_contract(self):
        """Test segment extraction with render contract parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir)

            captured_cmd = []

            def mock_run_ffmpeg(cmd, expected_duration=None):
                captured_cmd.append(cmd)
                return FfmpegResult(
                    success=True, returncode=0, stdout="", stderr="", duration_s=1.0
                )

            runner._run_ffmpeg = mock_run_ffmpeg

            # Extract with contract parameters
            runner.extract_segment(
                source_path="input.mp4",
                start=5.0,
                end=15.0,
                output_path="output.mp4",
                codec="libx264",
                profile="high",
                level="4.1",
                pixel_format="yuv420p",
                target_fps=30,
                crf=23,
            )

            cmd = captured_cmd[0]

            # Verify contract parameters
            assert "-profile:v" in cmd
            assert "high" in cmd
            assert "-level" in cmd
            assert "4.1" in cmd
            assert "-pix_fmt" in cmd
            assert "yuv420p" in cmd
            assert "-r" in cmd
            assert "30" in cmd
            assert "-vsync" in cmd
            assert "cfr" in cmd
            assert "-crf" in cmd
            assert "23" in cmd

    def test_concat_videos_command(self):
        """Test concat command generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir)

            captured_cmd = []

            def mock_run_ffmpeg(cmd, expected_duration=None):
                captured_cmd.append(cmd)
                return FfmpegResult(
                    success=True, returncode=0, stdout="", stderr="", duration_s=1.0
                )

            runner._run_ffmpeg = mock_run_ffmpeg

            # Concat videos
            input_files = ["clip1.mp4", "clip2.mp4", "clip3.mp4"]
            runner.concat_videos(input_files, "montage.mp4")

            cmd = captured_cmd[0]

            # Verify concat demuxer usage
            assert "-f" in cmd
            assert "concat" in cmd
            assert "-safe" in cmd
            assert "0" in cmd
            assert "-c" in cmd
            assert "copy" in cmd
            assert "montage.mp4" in cmd


class TestArtifactGeneration:
    """Test failure artifact generation."""

    def test_save_failure_artifacts(self):
        """Test that failure artifacts are saved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir, save_artifacts_on_failure=True)

            cmd = ["ffmpeg", "-i", "input.mp4", "output.mp4"]
            stdout = "FFmpeg output"
            stderr = "Error: File not found"

            artifacts = runner._save_failure_artifacts(cmd, stdout, stderr)

            # Verify artifacts were created
            assert len(artifacts) == 2

            # Check log file
            log_file = [a for a in artifacts if a.name.startswith("ffmpeg_error_")][0]
            assert log_file.exists()

            log_content = log_file.read_text()
            assert "COMMAND:" in log_content
            assert "ffmpeg" in log_content
            assert "STDOUT:" in log_content
            assert "FFmpeg output" in log_content
            assert "STDERR:" in log_content
            assert "Error: File not found" in log_content

            # Check script file
            script_file = [a for a in artifacts if a.name.startswith("ffmpeg_cmd_")][0]
            assert script_file.exists()
            assert os.access(script_file, os.X_OK)  # Executable

            script_content = script_file.read_text()
            assert "#!/bin/bash" in script_content
            assert "ffmpeg" in script_content


class TestTempDirectory:
    """Test temp directory handling."""

    def test_temp_dir_from_config(self):
        """Test using temp_dir from config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir)

            temp_dir = runner._get_temp_dir()
            assert str(temp_dir) == tmpdir

    def test_temp_dir_from_env(self):
        """Test using TMPDIR environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TMPDIR": tmpdir}):
                runner = FfmpegRunner(temp_dir=None)

                temp_dir = runner._get_temp_dir()
                assert str(temp_dir) == tmpdir

    def test_temp_dir_default_fallback(self):
        """Test fallback to /tmp."""
        # Clear TMPDIR if set
        with patch.dict(os.environ, {}, clear=True):
            runner = FfmpegRunner(temp_dir=None)

            temp_dir = runner._get_temp_dir()
            assert str(temp_dir) == "/tmp"


class TestProcessTreeCleanup:
    """Test process tree cleanup logic."""

    def test_kill_process_tree_with_psutil(self):
        """Test process tree kill with psutil available."""
        # Skip if psutil not installed (optional dependency)
        pytest.importorskip("psutil")

        runner = FfmpegRunner()

        # Mock process
        mock_process = MagicMock()
        runner._process = mock_process
        mock_process.pid = 12345

        # Mock psutil Process
        mock_parent = MagicMock()
        mock_child1 = MagicMock()
        mock_child2 = MagicMock()

        with patch("psutil.Process") as mock_process_class:
            mock_process_class.return_value = mock_parent
            mock_parent.children.return_value = [mock_child1, mock_child2]

            # Mock wait_procs
            with patch("psutil.wait_procs") as mock_wait:
                mock_wait.return_value = ([mock_parent], [])  # All processes terminated

                stdout, stderr = runner._kill_process_tree()

                # Verify terminate was called on all processes
                mock_parent.terminate.assert_called_once()
                mock_child1.terminate.assert_called_once()
                mock_child2.terminate.assert_called_once()

    def test_kill_process_tree_without_psutil(self):
        """Test process tree kill fallback without psutil."""
        runner = FfmpegRunner()

        # Mock process
        mock_process = MagicMock()
        runner._process = mock_process
        mock_process.pid = 12345
        mock_process.stdout = None
        mock_process.stderr = None

        # Mock psutil import failure
        with patch("builtins.__import__", side_effect=ImportError):
            with patch("os.name", "posix"):
                with patch("os.killpg") as mock_killpg:
                    with patch("os.getpgid", return_value=12345):
                        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)

                        runner._kill_process_tree()

                        # Verify SIGTERM was sent
                        assert mock_killpg.call_count >= 1


class TestConfigValidation:
    """Test configuration validation with Pydantic models."""

    def test_rendering_config_defaults(self):
        """Test RenderingConfig default values."""
        from content_ai.models import RenderingConfig

        config = RenderingConfig()

        assert config.global_timeout_s == 1800
        assert config.no_progress_timeout_s == 120
        assert config.max_retries == 2
        assert config.kill_grace_period_s == 5
        assert config.save_artifacts_on_failure is True
        assert config.ffmpeg_loglevel == "info"
        assert config.normalize_to_contract is True  # Enabled by default for VFR safety

    def test_video_codec_config_validation(self):
        """Test VideoCodecConfig validation."""
        from content_ai.models import VideoCodecConfig

        # Valid config
        config = VideoCodecConfig(
            codec="libx264",
            profile="high",
            level="4.1",
            pixel_format="yuv420p",
            target_fps=30,
            crf=23,
            preset="medium",
        )

        assert config.codec == "libx264"
        assert config.crf == 23

        # Invalid CRF (out of range)
        with pytest.raises(Exception):  # Pydantic ValidationError
            VideoCodecConfig(crf=100)

    def test_content_ai_config_includes_rendering(self):
        """Test that ContentAIConfig includes rendering section."""
        from content_ai.models import ContentAIConfig

        config = ContentAIConfig()

        assert hasattr(config, "rendering")
        assert config.rendering is not None
        assert config.rendering.global_timeout_s == 1800


class TestIntegration:
    """Integration tests with mocked FFmpeg."""

    @patch("subprocess.Popen")
    def test_extract_segment_success(self, mock_popen):
        """Test successful segment extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir)

            # Mock successful FFmpeg process
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.pid = 12345
            mock_process.communicate.return_value = ("", "")
            mock_process.stdout = None
            mock_process.stderr = iter([])  # Empty stderr

            mock_popen.return_value = mock_process

            result = runner.extract_segment(
                source_path="input.mp4", start=5.0, end=10.0, output_path="output.mp4"
            )

            assert result.success is True
            assert result.returncode == 0
            assert result.error_type is None

    @patch("subprocess.Popen")
    def test_extract_segment_failure(self, mock_popen):
        """Test segment extraction failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FfmpegRunner(temp_dir=tmpdir)

            # Mock failed FFmpeg process
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.pid = 12345
            mock_process.communicate.return_value = ("", "input.mp4: No such file or directory")
            mock_process.stdout = None
            mock_process.stderr = iter([])

            mock_popen.return_value = mock_process

            result = runner.extract_segment(
                source_path="nonexistent.mp4", start=0.0, end=10.0, output_path="output.mp4"
            )

            assert result.success is False
            assert result.returncode == 1
            assert result.error_type == FfmpegErrorType.PERMANENT
            assert len(result.artifacts_saved) == 2  # Log + script


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
