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


def test_cli_no_command_shows_help(capsys):
    """Test running with no command shows help."""
    with patch("sys.argv", ["content-ai"]):
        main()
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()
