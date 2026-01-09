import pytest
from pathlib import Path
import tempfile
from content_ai.scanner import scan_input


def test_scan_empty_directory():
    """Test scanning empty directory returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = scan_input(tmpdir, recursive=False)
        assert result == []


def test_scan_filters_non_video_files():
    """Test scanner ignores non-video files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "test.mp4").touch()
        (tmppath / "readme.txt").touch()
        (tmppath / "image.jpg").touch()

        result = scan_input(tmpdir, extensions=[".mp4"])
        assert len(result) == 1
        assert result[0].name == "test.mp4"


def test_scan_recursive_nested_dirs():
    """Test recursive scanning finds nested videos."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "sub1").mkdir()
        (tmppath / "sub1" / "video1.mp4").touch()
        (tmppath / "sub2").mkdir()
        (tmppath / "sub2" / "video2.mp4").touch()

        result = scan_input(tmpdir, recursive=True, extensions=[".mp4"])
        assert len(result) == 2


def test_scan_non_recursive_ignores_subdirs():
    """Test non-recursive scan only finds top-level files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "video1.mp4").touch()
        (tmppath / "sub").mkdir()
        (tmppath / "sub" / "video2.mp4").touch()

        result = scan_input(tmpdir, recursive=False, extensions=[".mp4"])
        assert len(result) == 1
        assert result[0].name == "video1.mp4"


def test_scan_single_file():
    """Test scanning a single file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        video_file = tmppath / "test.mp4"
        video_file.touch()

        result = scan_input(str(video_file))
        assert len(result) == 1
        assert result[0].name == "test.mp4"


def test_scan_nonexistent_path_raises():
    """Test scanning nonexistent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        scan_input("/nonexistent/path/video.mp4")


def test_scan_with_limit():
    """Test limit parameter restricts results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        for i in range(5):
            (tmppath / f"video{i}.mp4").touch()

        result = scan_input(tmpdir, limit=3, extensions=[".mp4"])
        assert len(result) == 3


def test_scan_default_extensions():
    """Test default video extensions are recognized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "test.mp4").touch()
        (tmppath / "test.mov").touch()
        (tmppath / "test.mkv").touch()
        (tmppath / "test.avi").touch()

        result = scan_input(tmpdir)
        assert len(result) == 4


def test_scan_custom_extensions():
    """Test custom extensions filter correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "test.mp4").touch()
        (tmppath / "test.webm").touch()

        result = scan_input(tmpdir, extensions=[".webm"])
        assert len(result) == 1
        assert result[0].suffix == ".webm"


def test_scan_extensions_case_insensitive():
    """Test extension matching is case-insensitive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / "test.MP4").touch()
        (tmppath / "test.MoV").touch()

        result = scan_input(tmpdir, extensions=[".mp4", ".mov"])
        assert len(result) == 2
