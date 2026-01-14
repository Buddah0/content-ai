import os
import json
import subprocess
from pathlib import Path
from moviepy.editor import VideoFileClip
from typing import List, Optional, Callable
from dataclasses import dataclass
import imageio_ffmpeg


def get_ffmpeg_cmd():
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_segment_to_file(
    source_path: str, start: float, end: float, output_path: str
):
    """
    Render a single segment to a temporary file.
    """
    # Use moviepy to cut and save
    # We use a context manager to ensure the source is closed
    with VideoFileClip(source_path) as video:
        # Clamp timestamps just in case
        start = max(0, start)
        end = min(video.duration, end)

        if end <= start:
            return  # Skip invalid

        new_clip = video.subclip(start, end)
        # using 'fast' preset for speed, crf for quality
        # audio_codec aac is standard
        new_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=f"temp_render_audio_{os.getpid()}.m4a",
            remove_temp=True,
            logger=None,
            preset="ultrafast",  # optimize for speed as requested "short form"
        )


def build_montage_from_list(segment_files: List[str], output_file: str):
    """
    Concatenate a list of video files using ffmpeg concat demuxer.
    """
    if not segment_files:
        return

    # Create list file
    list_path = f"concat_list_{os.getpid()}.txt"
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for path in segment_files:
                # FFMPEG requires absolute paths or relative. Let's use absolute.
                # Escape backslashes for Windows if needed, but forward slashes usually work.
                # 'file' keyword is required.
                abs_path = Path(path).resolve()
                f.write(f"file '{str(abs_path).replace(os.sep, '/')}'\n")

        # Run ffmpeg
        # ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
        ffmpeg_exe = get_ffmpeg_cmd()
        cmd = [
            ffmpeg_exe,
            "-y",  # overwrite
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            output_file,
        ]

        print(f"Running ffmpeg concat...")
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )

    except subprocess.CalledProcessError as e:
        print(f"FFMPEG Error: {e.stderr.decode() if e.stderr else 'Unknown'}")
        raise e
    except Exception as e:
        print(f"Error building montage: {e}")
        raise e
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)


def check_ffmpeg():
    """Verify ffmpeg is installed."""
    try:
        # Get path and verify it exists/runs
        exe = get_ffmpeg_cmd()
        subprocess.run(
            [exe, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return False


# ============================================================================
# FFmpeg Runner Integration (PR #3)
# ============================================================================


def render_segment_with_runner(
    source_path: str,
    start: float,
    end: float,
    output_path: str,
    rendering_config: Optional["RenderingConfig"] = None,
    progress_callback: Optional[Callable[["FfmpegProgress"], None]] = None
) -> "FfmpegResult":
    """Render a segment using FfmpegRunner with full timeout/progress support.

    This is the recommended function for production rendering. It provides:
    - Process isolation (no zombie FFmpeg processes)
    - Dual timeout enforcement (global + no-progress)
    - Real-time progress monitoring
    - Error classification for retry logic
    - Artifact preservation on failure
    - VFR detection and CFR normalization

    Args:
        source_path: Input video file path
        start: Start time in seconds
        end: End time in seconds
        output_path: Output file path
        rendering_config: RenderingConfig (uses defaults if None)
        progress_callback: Optional callback for progress updates

    Returns:
        FfmpegResult with success status, error info, and artifacts

    Example:
        >>> from content_ai.renderer import render_segment_with_runner
        >>> from content_ai.models import RenderingConfig
        >>>
        >>> def on_progress(p):
        ...     print(f"Progress: {p.current_time_s:.1f}s @ {p.fps:.0f}fps")
        >>>
        >>> result = render_segment_with_runner(
        ...     "input.mp4", 10.0, 20.0, "output.mp4",
        ...     progress_callback=on_progress
        ... )
        >>> if result.success:
        ...     print("Segment rendered successfully")
        ... else:
        ...     print(f"Error: {result.error_type}")
    """
    from .ffmpeg_runner import FfmpegRunner, FfmpegProgress, FfmpegResult
    from .models import RenderingConfig

    # Use defaults if no config provided
    if rendering_config is None:
        rendering_config = RenderingConfig()

    # Check if we should probe source for VFR detection
    source_metadata = None
    use_fast_path = False

    if rendering_config.fast_path_enabled:
        try:
            source_metadata = probe_video(
                source_path,
                frame_rate_tolerance=rendering_config.vfr_detection.frame_rate_tolerance
            )
            use_fast_path = should_use_fast_path(
                source_metadata,
                normalize_to_contract=rendering_config.normalize_to_contract,
                force_cfr=rendering_config.force_cfr,
                fast_path_enabled=rendering_config.fast_path_enabled
            )
        except RuntimeError as e:
            # If probe fails, fall back to full re-encode for safety
            print(f"Warning: Could not probe source video: {e}")
            use_fast_path = False

    # Create runner with config settings
    runner = FfmpegRunner(
        global_timeout_s=rendering_config.global_timeout_s,
        no_progress_timeout_s=rendering_config.no_progress_timeout_s,
        max_retries=rendering_config.max_retries,
        kill_grace_period_s=rendering_config.kill_grace_period_s,
        save_artifacts_on_failure=rendering_config.save_artifacts_on_failure,
        ffmpeg_loglevel=rendering_config.ffmpeg_loglevel,
        temp_dir=rendering_config.temp_dir,
        progress_callback=progress_callback
    )

    # Get contract settings
    contract = rendering_config.contract
    video_config = contract.video_codec
    audio_config = contract.audio_codec

    # Extract segment with appropriate settings
    if use_fast_path and not rendering_config.normalize_to_contract:
        # Fast path: stream copy (no re-encode)
        # Note: FfmpegRunner doesn't have a direct stream-copy extract method,
        # so we use the standard extract but with source codec settings
        return runner.extract_segment(
            source_path=source_path,
            start=start,
            end=end,
            output_path=output_path,
            codec="copy",  # Stream copy for fast path
            preset="medium",  # Ignored for copy
            audio_codec="copy"  # Stream copy audio too
        )
    else:
        # Full re-encode to contract specs
        return runner.extract_segment(
            source_path=source_path,
            start=start,
            end=end,
            output_path=output_path,
            codec=video_config.codec,
            preset=video_config.preset,
            audio_codec=audio_config.codec,
            profile=video_config.profile,
            level=video_config.level,
            pixel_format=video_config.pixel_format,
            target_fps=video_config.target_fps if rendering_config.force_cfr else None,
            crf=video_config.crf
        )


def concat_with_runner(
    segment_files: List[str],
    output_path: str,
    rendering_config: Optional["RenderingConfig"] = None,
    progress_callback: Optional[Callable[["FfmpegProgress"], None]] = None
) -> "FfmpegResult":
    """Concatenate segments using FfmpegRunner with validation.

    This function validates segment compatibility before concat to ensure
    stream copy is safe. If segments are incompatible, it logs a warning
    but proceeds (segments were already re-encoded by render_segment_with_runner).

    Args:
        segment_files: List of segment file paths
        output_path: Output file path
        rendering_config: RenderingConfig (uses defaults if None)
        progress_callback: Optional callback for progress updates

    Returns:
        FfmpegResult with success status

    Example:
        >>> from content_ai.renderer import concat_with_runner
        >>>
        >>> segments = ["clip_000.mp4", "clip_001.mp4", "clip_002.mp4"]
        >>> result = concat_with_runner(segments, "montage.mp4")
        >>> if result.success:
        ...     print(f"Created montage at {output_path}")
    """
    from .ffmpeg_runner import FfmpegRunner, FfmpegProgress, FfmpegResult
    from .models import RenderingConfig

    if not segment_files:
        # Return empty success for no segments
        return FfmpegResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="No segments to concatenate",
            duration_s=0.0
        )

    # Use defaults if no config provided
    if rendering_config is None:
        rendering_config = RenderingConfig()

    # Validate segments before concat (optional but recommended)
    if rendering_config.validate_before_concat:
        try:
            compatible = validate_segment_compatibility(
                segment_files,
                frame_rate_tolerance=rendering_config.vfr_detection.frame_rate_tolerance
            )
            if not compatible:
                print("Warning: Segments have incompatible specs. Proceeding with concat anyway.")
        except RuntimeError as e:
            print(f"Warning: Could not validate segments: {e}")

    # Create runner with config settings
    runner = FfmpegRunner(
        global_timeout_s=rendering_config.global_timeout_s,
        no_progress_timeout_s=rendering_config.no_progress_timeout_s,
        max_retries=rendering_config.max_retries,
        kill_grace_period_s=rendering_config.kill_grace_period_s,
        save_artifacts_on_failure=rendering_config.save_artifacts_on_failure,
        ffmpeg_loglevel=rendering_config.ffmpeg_loglevel,
        temp_dir=rendering_config.temp_dir,
        progress_callback=progress_callback
    )

    return runner.concat_videos(segment_files, output_path)


# ============================================================================
# VFR Detection + Normalization Functions (PR #2)
# ============================================================================


@dataclass
class VideoMetadata:
    """Video metadata from ffprobe.

    Used for VFR detection, codec compatibility checking, and fast path decisions.
    """
    # Video stream info
    codec_name: str
    profile: Optional[str]
    level: Optional[int]
    pixel_format: str
    width: int
    height: int

    # Frame rate info
    r_frame_rate: str           # Container/declared frame rate (e.g., "60/1")
    avg_frame_rate: str         # Actual average frame rate (e.g., "1349280/22481")
    is_vfr: bool                # True if avg != r_frame_rate (within tolerance)
    fps_numeric: float          # Numeric fps for easy comparison

    # Audio stream info
    audio_codec: Optional[str]
    audio_sample_rate: Optional[int]
    audio_channels: Optional[int]

    # File info
    duration: float
    bitrate: Optional[int]


def probe_video(video_path: str, frame_rate_tolerance: float = 0.01) -> VideoMetadata:
    """Probe video file using ffprobe to extract codec/fps metadata.

    Args:
        video_path: Path to video file
        frame_rate_tolerance: Tolerance for VFR detection (default: 0.01 = 1%)

    Returns:
        VideoMetadata with codec, fps, and VFR detection.

    Raises:
        RuntimeError: If ffprobe fails or video has no video stream.

    Example:
        >>> metadata = probe_video("gameplay.mp4")
        >>> if metadata.is_vfr:
        ...     print(f"VFR detected! {metadata.r_frame_rate} vs {metadata.avg_frame_rate}")
        >>> print(f"Codec: {metadata.codec_name}, FPS: {metadata.fps_numeric}")
    """
    # Use ffprobe (same directory as ffmpeg)
    ffmpeg_exe = get_ffmpeg_cmd()
    ffprobe_exe = ffmpeg_exe.replace("ffmpeg", "ffprobe")

    cmd = [
        ffprobe_exe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            text=True,
            timeout=30  # ffprobe should be fast
        )
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"ffprobe output parsing failed: {e}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out after 30s")

    # Find video and audio streams
    video_stream = None
    audio_stream = None

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream

    if not video_stream:
        raise RuntimeError(f"No video stream found in {video_path}")

    # Extract video metadata
    r_frame_rate = video_stream.get("r_frame_rate", "0/1")
    avg_frame_rate = video_stream.get("avg_frame_rate", "0/1")

    # Convert frame rates to numeric
    def fraction_to_float(rate_str: str) -> float:
        """Convert '60/1' or '1349280/22481' to float."""
        try:
            num, denom = rate_str.split("/")
            return float(num) / float(denom) if float(denom) != 0 else 0.0
        except:
            return 0.0

    r_fps = fraction_to_float(r_frame_rate)
    avg_fps = fraction_to_float(avg_frame_rate)

    # VFR detection: compare r_frame_rate vs avg_frame_rate
    # If they differ by more than tolerance, it's VFR
    if r_fps > 0:
        fps_diff = abs(r_fps - avg_fps) / r_fps
        is_vfr = fps_diff > frame_rate_tolerance
    else:
        is_vfr = False

    # Extract format duration
    format_info = data.get("format", {})
    duration = float(format_info.get("duration", 0))
    bitrate = int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else None

    # Audio metadata
    audio_codec = audio_stream.get("codec_name") if audio_stream else None
    audio_sample_rate = int(audio_stream.get("sample_rate", 0)) if audio_stream else None
    audio_channels = audio_stream.get("channels") if audio_stream else None

    return VideoMetadata(
        codec_name=video_stream.get("codec_name", "unknown"),
        profile=video_stream.get("profile"),
        level=video_stream.get("level"),
        pixel_format=video_stream.get("pix_fmt", "unknown"),
        width=video_stream.get("width", 0),
        height=video_stream.get("height", 0),
        r_frame_rate=r_frame_rate,
        avg_frame_rate=avg_frame_rate,
        is_vfr=is_vfr,
        fps_numeric=avg_fps if avg_fps > 0 else r_fps,
        audio_codec=audio_codec,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        duration=duration,
        bitrate=bitrate
    )


def should_use_fast_path(
    source_metadata: VideoMetadata,
    normalize_to_contract: bool = False,
    force_cfr: bool = True,
    fast_path_enabled: bool = True
) -> bool:
    """Determine if fast path (-c copy) can be used for extraction.

    Fast path is safe when source already matches the render contract specs.

    Args:
        source_metadata: Video metadata from probe_video()
        normalize_to_contract: If True, always normalize (no fast path)
        force_cfr: If True, reject VFR sources
        fast_path_enabled: Global fast path toggle

    Returns:
        True if fast path is safe, False if normalization required.

    Example:
        >>> metadata = probe_video("video.mp4")
        >>> if should_use_fast_path(metadata):
        ...     print("Using fast path (-c copy)")
        ... else:
        ...     print("Normalizing to contract")
    """
    # Check if fast path is globally enabled
    if not fast_path_enabled:
        return False

    # Check if normalization is forced
    if normalize_to_contract:
        return False

    # VFR check - reject if force_cfr enabled
    if force_cfr and source_metadata.is_vfr:
        return False  # VFR source needs normalization to CFR

    # Fast path is safe
    # Note: In PR #3, we'll add codec/profile/fps checks against the contract
    # For PR #2, we're just implementing VFR detection
    return True


def validate_segment_compatibility(
    segment_paths: List[str],
    frame_rate_tolerance: float = 0.01
) -> bool:
    """Validate that all segments have identical codec/fps/audio specs.

    This should be called before concat to ensure -c copy is safe.

    Args:
        segment_paths: List of segment file paths
        frame_rate_tolerance: Tolerance for VFR detection

    Returns:
        True if all compatible, False otherwise

    Raises:
        RuntimeError: If probing fails

    Example:
        >>> segments = ["clip_000.mp4", "clip_001.mp4", "clip_002.mp4"]
        >>> if validate_segment_compatibility(segments):
        ...     # Safe to concat with -c copy
        ...     build_montage_from_list(segments, "montage.mp4")
        ... else:
        ...     print("Warning: Incompatible segments detected")
    """
    if not segment_paths:
        return True

    # Probe first segment as reference
    reference = probe_video(segment_paths[0], frame_rate_tolerance)

    for path in segment_paths[1:]:
        meta = probe_video(path, frame_rate_tolerance)

        # Compare critical fields
        if meta.codec_name != reference.codec_name:
            print(f"Warning: Codec mismatch - {meta.codec_name} vs {reference.codec_name}")
            return False

        if meta.pixel_format != reference.pixel_format:
            print(f"Warning: Pixel format mismatch - {meta.pixel_format} vs {reference.pixel_format}")
            return False

        if abs(meta.fps_numeric - reference.fps_numeric) > 0.01:
            print(f"Warning: FPS mismatch - {meta.fps_numeric} vs {reference.fps_numeric}")
            return False

        if meta.is_vfr or reference.is_vfr:
            print(f"Warning: VFR detected in segments")
            return False

        if meta.audio_codec != reference.audio_codec:
            print(f"Warning: Audio codec mismatch - {meta.audio_codec} vs {reference.audio_codec}")
            return False

        if meta.audio_sample_rate != reference.audio_sample_rate:
            print(f"Warning: Audio sample rate mismatch - {meta.audio_sample_rate} vs {reference.audio_sample_rate}")
            return False

    return True
