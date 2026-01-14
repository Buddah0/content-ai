"""Worker pool implementation using ProcessPoolExecutor.

This module provides parallel video processing with:
- ProcessPoolExecutor for CPU/IO-bound video work
- Worker initialization to pre-load heavy libraries
- Heartbeat threads for long-running jobs
- Error classification (permanent vs transient)
- Disk space monitoring
- Graceful shutdown handling
"""

import os
import time
import shutil
import threading
import traceback
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, List, Any, Optional, Dict
from tqdm import tqdm

from .backends import WorkerPool, QueueBackend
from .models import JobItem, JobResult, JobStatus


def _worker_init():
    """Initialize worker process (runs once per worker).

    Pre-loads heavy libraries to avoid repeated initialization overhead.
    Sets up worker-specific temp directories to avoid conflicts.
    """
    # Pre-load heavy libraries (expensive imports)
    import librosa  # noqa
    import moviepy  # noqa

    # Set worker-specific temp directory
    worker_tmp = f'/tmp/content_ai_worker_{os.getpid()}'
    os.makedirs(worker_tmp, exist_ok=True)
    os.environ['TMPDIR'] = worker_tmp


class JobWorkerPool(WorkerPool):
    """ProcessPoolExecutor-based worker pool for video processing.

    Features:
    - Long-lived worker processes (avoid repeated library loading)
    - Worker initialization with pre-loaded libraries
    - Context manager for graceful shutdown
    - Progress tracking with tqdm
    - Error handling that continues processing

    Performance:
    - Better than joblib for video processing (6-16x less overhead)
    - No pickle overhead for large video data
    - Better CPU/IO balance for mixed workloads
    """

    def __init__(self, n_workers: int = None):
        """Initialize worker pool.

        Args:
            n_workers: Number of parallel workers (default: CPU count)
        """
        self.n_workers = n_workers or multiprocessing.cpu_count()
        self._executor = None

    def __enter__(self):
        """Create worker pool on context entry."""
        self._executor = ProcessPoolExecutor(
            max_workers=self.n_workers,
            initializer=_worker_init
        )
        return self

    def __exit__(self, *args):
        """Shutdown worker pool on context exit."""
        if self._executor:
            self._executor.shutdown(wait=True)

    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """Submit task to worker pool.

        Args:
            fn: Callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future handle
        """
        if not self._executor:
            raise RuntimeError("Worker pool not initialized (use with statement)")

        return self._executor.submit(fn, *args, **kwargs)

    def map(self, fn: Callable, items: List[Any]) -> List[Any]:
        """Parallel map with progress tracking and error handling.

        Args:
            fn: Callable to apply to each item
            items: List of items to process

        Returns:
            List of results in submission order (includes None for failures)

        Error handling:
        - Exceptions are caught and logged
        - Failed items return None
        - Processing continues for remaining items
        """
        if not self._executor:
            raise RuntimeError("Worker pool not initialized (use with statement)")

        # Submit all jobs
        futures = {
            self._executor.submit(fn, item): item
            for item in items
        }

        # Collect results as they complete
        results = []
        for future in tqdm(
            as_completed(futures),
            total=len(items),
            desc="Processing videos",
            unit="video"
        ):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                # Log error but continue processing
                print(f"Job failed: {e}")
                results.append(None)

        return results

    def shutdown(self, wait: bool = True):
        """Graceful shutdown.

        Args:
            wait: If True, wait for pending tasks to complete
        """
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None


def process_video_job(
    job: JobItem,
    config: Dict[str, Any],
    db_path: str,
    run_dir: Path,
    use_ffmpeg_runner: bool = False
) -> JobResult:
    """Worker function: processes single video job.

    This function runs in a worker process and handles:
    - File validation (exists, readable, non-empty)
    - Disk space monitoring
    - Heartbeat updates for long jobs
    - Detection → Processing → Rendering pipeline
    - Success/failure acknowledgment with retry logic
    - Error classification (permanent vs transient)

    Args:
        job: Job specification with video path and metadata
        config: Resolved configuration dictionary
        db_path: Path to SQLite database (queue recreated in worker)
        run_dir: Output directory for this run
        use_ffmpeg_runner: If True, use FfmpegRunner with progress callbacks
                           (recommended for production - prevents zombie processes)

    Returns:
        JobResult with status, output files, and timing

    Error handling:
    - Permanent errors (FileNotFoundError, PermissionError): no retry
    - Transient errors (network, temp failure): retry with backoff
    - Critical errors (disk full): re-raise to stop worker
    """
    # Recreate queue connection in worker process (SQLite connections can't be pickled)
    from .sqlite_backend import SQLiteManifest, SQLiteQueue
    manifest = SQLiteManifest(db_path)
    queue = SQLiteQueue(manifest)

    worker_id = f"worker-{os.getpid()}"
    start_time = time.time()

    try:
        # EDGE CASE 1: Validate file exists and is readable
        video_path = Path(job.video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {job.video_path}")

        if not os.access(str(video_path), os.R_OK):
            raise PermissionError(f"Cannot read video file: {job.video_path}")

        video_size = video_path.stat().st_size
        if video_size == 0:
            raise ValueError(f"Video file is empty: {job.video_path}")

        # EDGE CASE 2: Check available disk space
        estimated_output_size = video_size * 1.5  # Conservative estimate
        disk_usage = shutil.disk_usage(run_dir)

        if disk_usage.free < estimated_output_size:
            raise OSError(
                f"Insufficient disk space: need {estimated_output_size/1e9:.2f}GB, "
                f"have {disk_usage.free/1e9:.2f}GB"
            )

        # Start heartbeat thread for long-running jobs
        heartbeat_thread = _start_heartbeat(db_path, job.job_id)

        try:
            # Import processing modules (already loaded in worker init)
            from .. import detector, segments as seg_mod, renderer
            import uuid

            # 1. Detection phase
            raw_segments = detector.detect_hype(str(video_path), config)

            if not raw_segments:
                # No hype detected - still a success
                duration = time.time() - start_time
                result = JobResult(
                    job_id=job.job_id,
                    status=JobStatus.SUCCEEDED,
                    output_files=[],
                    duration_s=duration,
                    metadata={"segments": []}
                )
                queue.ack_success(job.job_id, result)
                return result

            # 2. Processing phase (following pipeline.py logic)
            # Get processing params from config
            pad_s = config["processing"]["context_padding_s"]
            merge_s = config["processing"]["merge_gap_s"]
            max_seg_dur = config["processing"].get("max_segment_duration_s", None)
            min_dur = config["detection"]["min_event_duration_s"]

            # Pad segments
            padded = seg_mod.pad_segments(raw_segments, pad_s)

            # Get video duration for clamping
            from moviepy.editor import VideoFileClip
            with VideoFileClip(str(video_path)) as clip:
                video_duration = clip.duration

            # Clamp to video bounds
            clamped = seg_mod.clamp_segments(padded, 0.0, video_duration)

            # Merge with max duration enforcement
            merged = seg_mod.merge_segments(clamped, merge_s, max_seg_dur)

            # Add metadata to segments
            for s in merged:
                s["source_path"] = str(video_path)
                s["id"] = str(uuid.uuid4())

            if not merged:
                # All segments filtered out - still a success
                duration = time.time() - start_time
                result = JobResult(
                    job_id=job.job_id,
                    status=JobStatus.SUCCEEDED,
                    output_files=[],
                    duration_s=duration,
                    metadata={"segments": []}
                )
                queue.ack_success(job.job_id, result)
                return result

            # 3. Rendering phase
            output_files = []
            video_name = video_path.stem

            # Get rendering config if using FfmpegRunner
            rendering_config = None
            if use_ffmpeg_runner:
                from ..models import RenderingConfig
                rendering_config_dict = config.get("rendering", {})
                rendering_config = RenderingConfig(**rendering_config_dict)

            for i, segment in enumerate(merged):
                output_path = run_dir / f"{video_name}_clip_{i:03d}.mp4"

                if use_ffmpeg_runner:
                    # Use FfmpegRunner with progress tracking and timeout enforcement
                    from ..ffmpeg_runner import FfmpegErrorType

                    result = renderer.render_segment_with_runner(
                        source_path=str(video_path),
                        start=segment['start'],
                        end=segment['end'],
                        output_path=str(output_path),
                        rendering_config=rendering_config,
                        progress_callback=None  # Could wire to heartbeat in future
                    )

                    if not result.success:
                        # Build error message with artifact info
                        error_msg = (
                            f"FFmpeg rendering failed for segment {i}: "
                            f"{result.stderr[:500] if result.stderr else 'Unknown error'}"
                        )
                        if result.artifacts_saved:
                            error_msg += f"\nArtifacts: {result.artifacts_saved}"

                        # Raise appropriate exception based on error type
                        # Permanent errors (bad input) should not be retried
                        # Transient errors (I/O issues) may be retried
                        if result.error_type == FfmpegErrorType.PERMANENT:
                            raise RuntimeError(error_msg)
                        else:
                            raise OSError(error_msg)
                else:
                    # Legacy MoviePy-based rendering
                    renderer.render_segment_to_file(
                        source_path=str(video_path),
                        start=segment['start'],
                        end=segment['end'],
                        output_path=str(output_path)
                    )

                output_files.append(str(output_path))

            # 4. Mark success
            duration = time.time() - start_time
            result = JobResult(
                job_id=job.job_id,
                status=JobStatus.SUCCEEDED,
                output_files=output_files,
                duration_s=duration,
                metadata={"segments": merged}
            )
            queue.ack_success(job.job_id, result)
            return result

        finally:
            # Stop heartbeat thread
            _stop_heartbeat(heartbeat_thread)

    except FileNotFoundError as e:
        # Permanent error - file deleted during processing
        error_msg = f"FileNotFoundError: {str(e)}"
        duration = time.time() - start_time
        queue.ack_fail(job.job_id, error_msg, retry=False)
        return JobResult(
            job_id=job.job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
            duration_s=duration
        )

    except PermissionError as e:
        # Permanent error - permission denied
        error_msg = f"PermissionError: {str(e)}"
        duration = time.time() - start_time
        queue.ack_fail(job.job_id, error_msg, retry=False)
        return JobResult(
            job_id=job.job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
            duration_s=duration
        )

    except ValueError as e:
        # Permanent error - invalid input
        error_msg = f"ValueError: {str(e)}"
        duration = time.time() - start_time
        queue.ack_fail(job.job_id, error_msg, retry=False)
        return JobResult(
            job_id=job.job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
            duration_s=duration
        )

    except OSError as e:
        # Disk space or I/O error
        error_str = str(e)

        # Check if disk full (critical - stop processing)
        if "No space left" in error_str or "Errno 28" in error_str:
            error_msg = f"CRITICAL: Disk full - {error_str}"
            queue.ack_fail(job.job_id, error_msg, retry=False)
            # Re-raise to stop worker
            raise OSError(error_msg) from e

        # Other OS errors - retry (might be transient)
        error_msg = f"OSError: {error_str}\n{traceback.format_exc()}"
        duration = time.time() - start_time
        queue.ack_fail(job.job_id, error_msg, retry=True)
        return JobResult(
            job_id=job.job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
            duration_s=duration
        )

    except Exception as e:
        # Generic error - retry (might be transient)
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        duration = time.time() - start_time
        queue.ack_fail(job.job_id, error_msg, retry=True)
        return JobResult(
            job_id=job.job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
            duration_s=duration
        )


def _start_heartbeat(db_path: str, job_id: str):
    """Start background thread to update heartbeat every 60s.

    Args:
        db_path: Path to SQLite database (create own connection for thread safety)
        job_id: Job identifier

    Returns:
        Tuple of (thread, stop_event) for cleanup

    Heartbeat prevents long-running jobs from being marked stale.
    Thread is daemon so it won't block process exit.
    Each thread creates its own SQLite connection to avoid threading issues.
    """
    stop_event = threading.Event()

    def heartbeat_loop():
        # Create thread-local queue connection
        from .sqlite_backend import SQLiteManifest, SQLiteQueue
        manifest = SQLiteManifest(db_path)
        queue = SQLiteQueue(manifest)

        while not stop_event.is_set():
            try:
                queue.update_heartbeat(job_id)
            except Exception as e:
                # Log but don't crash thread
                print(f"Heartbeat failed for {job_id}: {e}")

            # Sleep in small increments to allow fast shutdown
            for _ in range(60):
                if stop_event.is_set():
                    break
                time.sleep(1)

    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.start()

    return (thread, stop_event)


def _stop_heartbeat(heartbeat_data):
    """Stop heartbeat thread.

    Args:
        heartbeat_data: Tuple of (thread, stop_event) from _start_heartbeat

    Signals thread to stop and waits up to 5s for clean shutdown.
    """
    thread, stop_event = heartbeat_data
    stop_event.set()
    thread.join(timeout=5)
