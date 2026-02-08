from pathlib import Path
from unittest.mock import patch

import pytest

from content_ai.cli import main


def test_cli_help_displays():
    """Test --help works without errors."""
    with patch("sys.argv", ["content-ai", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_cli_scan_help():
    """Test scan subcommand help."""
    with patch("sys.argv", ["content-ai", "scan", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_cli_check_help():
    """Test check subcommand help."""
    with patch("sys.argv", ["content-ai", "check", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_cli_check_command_ffmpeg_found(capsys):
    """Test check command when ffmpeg is found."""
    with patch("sys.argv", ["content-ai", "check"]):
        with patch("content_ai.renderer.check_ffmpeg", return_value=True):
            main()
            captured = capsys.readouterr()
            assert "ffmpeg found" in captured.out.lower()


def test_cli_check_command_ffmpeg_not_found(capsys):
    """Test check command when ffmpeg is not found."""
    with patch("sys.argv", ["content-ai", "check"]):
        with patch("content_ai.renderer.check_ffmpeg", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "not found" in captured.out.lower()


# --- Default mode (zero-friction) tests ---


def test_cli_no_command_runs_default_mode():
    """Test running with no command routes to default mode (queue pipeline)."""
    with patch("sys.argv", ["content-ai"]):
        with patch("content_ai.queued_pipeline.run_queued_scan") as mock_run:
            main()
            mock_run.assert_called_once()
            cli_dict = mock_run.call_args[0][0]
            assert cli_dict["recursive"] is True
            assert Path(cli_dict["input"]).is_absolute()


def test_cli_default_mode_with_path(tmp_path):
    """Test default mode with explicit path."""
    with patch("sys.argv", ["content-ai", str(tmp_path)]):
        with patch("content_ai.queued_pipeline.run_queued_scan") as mock_run:
            main()
            mock_run.assert_called_once()
            cli_dict = mock_run.call_args[0][0]
            assert str(tmp_path) in cli_dict["input"]
            assert cli_dict["recursive"] is True


def test_cli_default_mode_nonexistent_path():
    """Test default mode with nonexistent path exits with error."""
    with patch("sys.argv", ["content-ai", "/nonexistent/path/xyz"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_cli_default_mode_with_flags(tmp_path):
    """Test default mode passes flags through correctly."""
    with patch(
        "sys.argv",
        ["content-ai", str(tmp_path), "--force", "-w", "4", "--rms-threshold", "0.15"],
    ):
        with patch("content_ai.queued_pipeline.run_queued_scan") as mock_run:
            main()
            cli_dict = mock_run.call_args[0][0]
            assert cli_dict["force"] is True
            assert cli_dict["workers"] == 4
            assert cli_dict["rms_threshold"] == 0.15


def test_cli_default_mode_recursive_always_on(tmp_path):
    """Test that recursive is always enabled in default mode."""
    with patch("sys.argv", ["content-ai", str(tmp_path)]):
        with patch("content_ai.queued_pipeline.run_queued_scan") as mock_run:
            main()
            cli_dict = mock_run.call_args[0][0]
            assert cli_dict["recursive"] is True


def test_cli_existing_subcommands_still_work():
    """Test that existing subcommands route to subcommand mode."""
    with patch("sys.argv", ["content-ai", "process", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
