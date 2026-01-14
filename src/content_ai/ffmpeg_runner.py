"""FFmpeg runner with process isolation, timeout enforcement, and progress monitoring.

This module provides robust FFmpeg orchestration that prevents zombie processes,
enforces timeouts, monitors progress, and preserves failure artifacts for debugging.

Key Features:
- Process isolation with subprocess.Popen
- Dual timeout enforcement (global + no-progress)
- Real-time progress parsing from FFmpeg stderr
- Cross-platform process tree cleanup (POSIX + Windows)
- Error classification for retry logic
- Artifact preservation on failure
"""

import os
import re
import time
import signal
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class FfmpegErrorType(Enum):
    """FFmpeg error classification for retry logic."""
    PERMANENT = "permanent"     # File not found, invalid format, codec error
    TRANSIENT = "transient"     # Network timeout, disk I/O stall
    TIMEOUT = "timeout"         # Process timeout (global or no-progress)
    PROCESS_KILLED = "killed"   # SIGTERM/SIGKILL cleanup


@dataclass
class FfmpegProgress:
    """Real-time FFmpeg progress metrics."""
    current_time_s: float = 0.0      # Current position in seconds
    total_duration_s: float = 0.0    # Total duration (if known)
    fps: float = 0.0                 # Current FPS
    bitrate_kbps: float = 0.0        # Current bitrate
    speed: float = 0.0               # Processing speed multiplier (e.g., 2.5x)
    frame: int = 0                   # Current frame number
    last_update: float = 0.0         # Timestamp of last update


@dataclass
class FfmpegResult:
    """Result of FFmpeg execution."""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    error_type: Optional[FfmpegErrorType] = None
    final_progress: Optional[FfmpegProgress] = None
    artifacts_saved: List[Path] = field(default_factory=list)


class FfmpegRunner:
    """Production-grade FFmpeg orchestration with timeout and zombie prevention.

    Features:
    - Process isolation with subprocess.Popen
    - Global timeout + no-progress timeout enforcement
    - Real-time progress parsing from stderr
    - Process tree cleanup (cross-platform)
    - Error classification for retry logic
    - Artifact preservation on failure
    - Integration with worker heartbeat

    Example:
        >>> from content_ai.ffmpeg_runner import FfmpegRunner, FfmpegProgress
        >>>
        >>> def progress_cb(progress: FfmpegProgress):
        ...     print(f"Progress: {progress.current_time_s:.1f}s @ {progress.fps}fps")
        >>>
        >>> runner = FfmpegRunner(
        ...     global_timeout_s=1800,
        ...     no_progress_timeout_s=120,
        ...     progress_callback=progress_cb
        ... )
        >>>
        >>> result = runner.extract_segment(
        ...     source_path="input.mp4",
        ...     start=10.0,
        ...     end=20.0,
        ...     output_path="output.mp4"
        ... )
        >>>
        >>> if result.success:
        ...     print("Segment extracted successfully")
        ... else:
        ...     print(f"Error: {result.error_type}")
        ...     print(f"Artifacts: {result.artifacts_saved}")
    """

    def __init__(
        self,
        global_timeout_s: int = 1800,
        no_progress_timeout_s: int = 120,
        max_retries: int = 2,
        kill_grace_period_s: int = 5,
        save_artifacts_on_failure: bool = True,
        ffmpeg_loglevel: str = "info",
        temp_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[FfmpegProgress], None]] = None
    ):
        """Initialize FFmpeg runner.

        Args:
            global_timeout_s: Maximum duration for any FFmpeg operation
            no_progress_timeout_s: Timeout if no progress update in N seconds
            max_retries: Number of retry attempts for transient errors
            kill_grace_period_s: Grace period between SIGTERM and SIGKILL
            save_artifacts_on_failure: Save logs and commands on failure
            ffmpeg_loglevel: FFmpeg log level (error, warning, info, verbose)
            temp_dir: Temporary directory for artifacts (None = use worker temp)
            progress_callback: Optional callback for progress updates
        """
        self.global_timeout_s = global_timeout_s
        self.no_progress_timeout_s = no_progress_timeout_s
        self.max_retries = max_retries
        self.kill_grace_period_s = kill_grace_period_s
        self.save_artifacts_on_failure = save_artifacts_on_failure
        self.ffmpeg_loglevel = ffmpeg_loglevel
        self.temp_dir = temp_dir
        self.progress_callback = progress_callback

        self._process: Optional[subprocess.Popen] = None
        self._progress = FfmpegProgress()
        self._stop_monitoring = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def extract_segment(
        self,
        source_path: str,
        start: float,
        end: float,
        output_path: str,
        codec: str = "libx264",
        preset: str = "medium",
        audio_codec: str = "aac",
        profile: Optional[str] = None,
        level: Optional[str] = None,
        pixel_format: Optional[str] = None,
        target_fps: Optional[int] = None,
        crf: Optional[int] = None
    ) -> FfmpegResult:
        """Extract video segment with frame-accurate seeking.

        Uses fast seek before input (-ss before -i) for performance.

        Args:
            source_path: Input video file
            start: Start time in seconds
            end: End time in seconds
            output_path: Output file path
            codec: Video codec (default: libx264)
            preset: Encoding preset (default: medium)
            audio_codec: Audio codec (default: aac)
            profile: H.264 profile (baseline, main, high)
            level: H.264 level (e.g., "4.1")
            pixel_format: Pixel format (e.g., "yuv420p")
            target_fps: Target frame rate for CFR (None = preserve source)
            crf: Constant Rate Factor (0-51, lower = better quality)

        Returns:
            FfmpegResult with success status and metadata
        """
        duration = end - start

        # Build FFmpeg command with progress reporting
        cmd = [
            self._get_ffmpeg_exe(),
            "-y",  # Overwrite output
            "-ss", str(start),  # Fast seek to start (before input)
            "-i", source_path,
            "-t", str(duration),  # Duration to extract
            "-c:v", codec,
            "-preset", preset,
            "-c:a", audio_codec,
        ]

        # Add optional video parameters
        if profile:
            cmd.extend(["-profile:v", profile])
        if level:
            cmd.extend(["-level", level])
        if pixel_format:
            cmd.extend(["-pix_fmt", pixel_format])
        if target_fps is not None:
            cmd.extend(["-r", str(target_fps)])
            cmd.extend(["-vsync", "cfr"])  # Force CFR
        if crf is not None:
            cmd.extend(["-crf", str(crf)])

        cmd.extend([
            "-progress", "pipe:2",  # Progress to stderr
            "-loglevel", self.ffmpeg_loglevel,
            output_path
        ])

        return self._run_ffmpeg(cmd, expected_duration=duration)

    def concat_videos(
        self,
        input_files: List[str],
        output_path: str
    ) -> FfmpegResult:
        """Concatenate videos using concat demuxer (stream copy).

        Args:
            input_files: List of video files to concatenate
            output_path: Output file path

        Returns:
            FfmpegResult with success status

        Raises:
            ValueError: If input_files is empty
        """
        if not input_files:
            raise ValueError("No input files provided for concatenation")

        # Create concat list file in temp directory
        temp_dir = self._get_temp_dir()
        list_path = temp_dir / f"concat_list_{os.getpid()}_{time.time():.0f}.txt"

        try:
            with open(list_path, "w", encoding="utf-8") as f:
                for path in input_files:
                    abs_path = Path(path).resolve()
                    # Escape single quotes for FFmpeg
                    escaped = str(abs_path).replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            # Build FFmpeg command
            cmd = [
                self._get_ffmpeg_exe(),
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",  # Stream copy (no re-encoding)
                "-progress", "pipe:2",
                "-loglevel", self.ffmpeg_loglevel,
                output_path
            ]

            result = self._run_ffmpeg(cmd)
            return result

        finally:
            # Cleanup concat list
            if list_path.exists():
                list_path.unlink()

    def _run_ffmpeg(
        self,
        cmd: List[str],
        expected_duration: Optional[float] = None
    ) -> FfmpegResult:
        """Execute FFmpeg with timeout enforcement and progress monitoring.

        Args:
            cmd: FFmpeg command as list
            expected_duration: Expected output duration for progress calculation

        Returns:
            FfmpegResult with execution details
        """
        start_time = time.time()
        self._progress = FfmpegProgress(total_duration_s=expected_duration or 0.0)

        try:
            # Start FFmpeg process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1  # Line buffered for real-time progress
            )

            # Start progress monitoring thread
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_progress,
                args=(self._process.stderr,),
                daemon=True
            )
            self._monitor_thread.start()

            # Enforce timeouts
            timeout_occurred = False
            timeout_type = None

            try:
                stdout, stderr = self._process.communicate(
                    timeout=self.global_timeout_s
                )
                returncode = self._process.returncode

            except subprocess.TimeoutExpired:
                # Global timeout exceeded
                timeout_occurred = True
                timeout_type = "global"
                stdout, stderr = self._kill_process_tree()
                returncode = -1

            # Check for no-progress timeout (only if process completed normally)
            if not timeout_occurred and self._progress.last_update > 0:
                time_since_progress = time.time() - self._progress.last_update
                if time_since_progress > self.no_progress_timeout_s:
                    timeout_occurred = True
                    timeout_type = "no_progress"
                    stdout_kill, stderr_kill = self._kill_process_tree()
                    # Append kill output to existing output
                    stdout = (stdout or "") + (stdout_kill or "")
                    stderr = (stderr or "") + (stderr_kill or "")
                    returncode = -1

            # Wait for monitor thread to finish
            self._stop_monitoring.set()
            if self._monitor_thread:
                self._monitor_thread.join(timeout=2)

            duration = time.time() - start_time

            # Classify error
            error_type = None
            if timeout_occurred:
                error_type = FfmpegErrorType.TIMEOUT
            elif returncode != 0:
                error_type = self._classify_error(stderr or "")

            # Save artifacts on failure
            artifacts = []
            if returncode != 0 and self.save_artifacts_on_failure:
                artifacts = self._save_failure_artifacts(cmd, stdout or "", stderr or "")

            return FfmpegResult(
                success=(returncode == 0),
                returncode=returncode,
                stdout=stdout or "",
                stderr=stderr or "",
                duration_s=duration,
                error_type=error_type,
                final_progress=self._progress,
                artifacts_saved=artifacts
            )

        except Exception as e:
            # Unexpected error - ensure cleanup
            self._kill_process_tree()
            raise

        finally:
            self._process = None
            self._stop_monitoring.set()

    def _monitor_progress(self, stderr_stream) -> None:
        """Monitor FFmpeg stderr for progress updates.

        Parses FFmpeg progress output and invokes callback.
        Updates self._progress for timeout detection.

        FFmpeg progress format:
            frame=  123
            fps=25.00
            bitrate=1234.5kbits/s
            out_time=00:00:05.123456
            speed=2.5x
            progress=continue
        """
        last_callback = 0.0

        try:
            for line in stderr_stream:
                if self._stop_monitoring.is_set():
                    break

                # Parse progress markers
                if "out_time=" in line:
                    # Parse time like "00:01:23.45"
                    match = re.search(r'out_time=(\d+):(\d+):(\d+)\.(\d+)', line)
                    if match:
                        h, m, s, cs = match.groups()
                        current_time = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                        self._progress.current_time_s = current_time
                        self._progress.last_update = time.time()

                if "frame=" in line:
                    match = re.search(r'frame=\s*(\d+)', line)
                    if match:
                        self._progress.frame = int(match.group(1))

                if "fps=" in line:
                    match = re.search(r'fps=\s*([\d.]+)', line)
                    if match:
                        self._progress.fps = float(match.group(1))

                if "bitrate=" in line:
                    match = re.search(r'bitrate=\s*([\d.]+)kbits/s', line)
                    if match:
                        self._progress.bitrate_kbps = float(match.group(1))

                if "speed=" in line:
                    match = re.search(r'speed=\s*([\d.]+)x', line)
                    if match:
                        self._progress.speed = float(match.group(1))

                # Invoke progress callback at configured interval
                now = time.time()
                if self.progress_callback and now - last_callback >= 2.0:
                    try:
                        self.progress_callback(self._progress)
                        last_callback = now
                    except Exception as e:
                        # Don't crash monitor thread on callback errors
                        print(f"Progress callback error: {e}")
        except Exception as e:
            # Don't crash on monitoring errors
            print(f"Progress monitoring error: {e}")

    def _kill_process_tree(self) -> Tuple[str, str]:
        """Kill FFmpeg process and all children (cross-platform).

        Kill sequence:
        1. Send SIGTERM to process group
        2. Wait grace period (default 5s)
        3. Send SIGKILL if still alive
        4. Collect stdout/stderr

        Returns:
            Tuple of (stdout, stderr)
        """
        if not self._process:
            return "", ""

        stdout_data = ""
        stderr_data = ""

        try:
            # Try psutil for robust process tree cleanup (if available)
            try:
                import psutil
                parent = psutil.Process(self._process.pid)
                children = parent.children(recursive=True)

                # Send SIGTERM to all processes
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                parent.terminate()

                # Wait for graceful shutdown
                gone, alive = psutil.wait_procs(
                    [parent] + children,
                    timeout=self.kill_grace_period_s
                )

                # Force kill survivors
                for p in alive:
                    try:
                        p.kill()
                    except psutil.NoSuchProcess:
                        pass

            except ImportError:
                # Fallback: manual process group kill
                if os.name == 'posix':
                    # Send SIGTERM to process group
                    try:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass

                    # Wait grace period
                    try:
                        self._process.wait(timeout=self.kill_grace_period_s)
                    except subprocess.TimeoutExpired:
                        # Force kill
                        try:
                            os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                else:
                    # Windows: terminate and force kill
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=self.kill_grace_period_s)
                    except subprocess.TimeoutExpired:
                        self._process.kill()

            # Collect output
            try:
                if self._process.stdout:
                    stdout_data = self._process.stdout.read()
                if self._process.stderr:
                    stderr_data = self._process.stderr.read()
            except Exception:
                pass

        except Exception as e:
            print(f"Error during process cleanup: {e}")

        return stdout_data, stderr_data

    def _classify_error(self, stderr: str) -> FfmpegErrorType:
        """Classify FFmpeg error for retry logic.

        Args:
            stderr: FFmpeg stderr output

        Returns:
            FfmpegErrorType for retry decision
        """
        stderr_lower = stderr.lower()

        # Permanent errors (no retry)
        permanent_patterns = [
            "no such file or directory",
            "invalid data found",
            "invalid argument",
            "permission denied",
            "unsupported codec",
            "invalid codec",
            "moov atom not found",
            "end of file",
            "corrupt",
        ]

        for pattern in permanent_patterns:
            if pattern in stderr_lower:
                return FfmpegErrorType.PERMANENT

        # Transient errors (retry)
        transient_patterns = [
            "i/o error",
            "connection refused",
            "connection timeout",
            "resource temporarily unavailable",
            "disk full",
        ]

        for pattern in transient_patterns:
            if pattern in stderr_lower:
                return FfmpegErrorType.TRANSIENT

        # Default: treat as transient (retry)
        return FfmpegErrorType.TRANSIENT

    def _save_failure_artifacts(
        self,
        cmd: List[str],
        stdout: str,
        stderr: str
    ) -> List[Path]:
        """Save debugging artifacts on FFmpeg failure.

        Creates:
        - ffmpeg_error_{timestamp}.log: Command + stdout + stderr
        - ffmpeg_cmd_{timestamp}.sh: Reproducible command script

        Args:
            cmd: FFmpeg command
            stdout: Process stdout
            stderr: Process stderr

        Returns:
            List of saved artifact paths
        """
        artifacts = []
        temp_dir = self._get_temp_dir()
        timestamp = int(time.time())

        # Save error log
        log_path = temp_dir / f"ffmpeg_error_{timestamp}.log"
        try:
            with open(log_path, "w") as f:
                f.write("=" * 80 + "\n")
                f.write("FFmpeg Error Log\n")
                f.write(f"Timestamp: {time.ctime()}\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write("=" * 80 + "\n\n")

                f.write("COMMAND:\n")
                f.write(" ".join(cmd) + "\n\n")

                f.write("STDOUT:\n")
                f.write(stdout or "(empty)\n\n")

                f.write("STDERR:\n")
                f.write(stderr or "(empty)\n\n")

            artifacts.append(log_path)
        except Exception as e:
            print(f"Failed to save error log: {e}")

        # Save reproducible command script
        script_path = temp_dir / f"ffmpeg_cmd_{timestamp}.sh"
        try:
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("# Reproducible FFmpeg command\n")
                f.write("# Generated: " + time.ctime() + "\n\n")

                # Properly escape command for shell
                escaped_cmd = []
                for arg in cmd:
                    if ' ' in arg or any(c in arg for c in ['$', '`', '"', '\\']):
                        escaped_cmd.append(f"'{arg}'")
                    else:
                        escaped_cmd.append(arg)

                f.write(" \\\n  ".join(escaped_cmd) + "\n")

            # Make executable
            script_path.chmod(0o755)
            artifacts.append(script_path)
        except Exception as e:
            print(f"Failed to save command script: {e}")

        return artifacts

    def _get_temp_dir(self) -> Path:
        """Get temporary directory (worker-specific if available)."""
        if self.temp_dir:
            temp_dir = Path(self.temp_dir)
        elif 'TMPDIR' in os.environ:
            # Use worker-specific temp dir
            temp_dir = Path(os.environ['TMPDIR'])
        else:
            temp_dir = Path("/tmp")

        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    @staticmethod
    def _get_ffmpeg_exe() -> str:
        """Get FFmpeg executable path."""
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
