"""Queue-based pipeline for resumable batch processing.

This module provides a higher-level API on top of the job queue system,
enabling batch processing of videos with automatic job creation, dirty
detection, crash recovery, and progress tracking.

Usage:
    # Enqueue a batch of videos
    queued_pipeline.enqueue_batch(
        video_files=["video1.mp4", "video2.mp4"],
        config=config,
        output_dir="output/batch_001"
    )

    # Process the queue
    queued_pipeline.process_queue(
        db_path="queue.db",
        n_workers=4
    )

    # Check status
    stats = queued_pipeline.get_queue_stats(db_path="queue.db")
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as config_lib
from . import scanner
from .queue import (
    JobItem,
    JobStatus,
    JobWorkerPool,
    SQLiteManifest,
    SQLiteQueue,
    compute_config_hash,
    compute_input_hash,
    process_video_job,
)


def enqueue_batch(
    video_files: List[Path],
    config: Dict[str, Any],
    output_dir: str,
    db_path: str = "queue.db",
    force: bool = False,
) -> Dict[str, Any]:
    """Enqueue a batch of videos for processing.

    This is the main entry point for queue-based processing. It:
    1. Computes hashes for dirty detection
    2. Checks manifest for cached results
    3. Enqueues new/modified videos
    4. Skips unchanged videos (unless force=True)

    Args:
        video_files: List of video file paths to process
        config: Resolved configuration dictionary
        output_dir: Base output directory for this batch
        db_path: Path to SQLite database (default: queue.db)
        force: If True, re-process all videos (ignore cache)

    Returns:
        Dictionary with enqueue statistics:
            - enqueued: Number of jobs enqueued
            - cached: Number of videos skipped (cached)
            - failed_hash: Number of videos that failed hashing
            - total: Total videos processed
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize queue and manifest
    manifest = SQLiteManifest(db_path)
    queue = SQLiteQueue(manifest)

    # Compute config hash once for entire batch
    config_hash = compute_config_hash(config)

    stats = {"enqueued": 0, "cached": 0, "failed_hash": 0, "total": len(video_files)}

    print(f"Enqueueing {len(video_files)} videos...")

    for video_path in video_files:
        try:
            # Compute input hash
            input_hash_data = compute_input_hash(str(video_path))

            # Check if we can skip (cached result)
            if not force:
                is_clean, reason = manifest.verify_hashes(
                    video_path=str(video_path),
                    config_hash=config_hash,
                    input_hashes=input_hash_data,
                )

                if is_clean:
                    print(f"  ✓ Cached: {video_path.name} ({reason})")
                    stats["cached"] += 1
                    continue
                else:
                    # Mark as dirty before re-enqueueing
                    print(f"  ⚠ Dirty: {video_path.name} ({reason})")
                    manifest.mark_dirty(str(video_path))

            # Create JobItem
            job_id = str(uuid.uuid4())

            # Convert config to dict if it's a Pydantic model
            config_dict = config
            if hasattr(config, "model_dump"):
                config_dict = config.model_dump()
            elif hasattr(config, "dict"):
                config_dict = config.dict()

            job_item = JobItem(
                job_id=job_id,
                video_path=str(video_path),
                input_hash_quick=input_hash_data["quick_hash"],
                input_hash_full=input_hash_data["full_hash"],
                input_size=input_hash_data["size"],
                config_hash=config_hash,
                status=JobStatus.PENDING,
                metadata={"config": config_dict, "output_dir": str(output_path)},
            )

            # Enqueue job
            queue.enqueue(job_item)

            print(f"  + Enqueued: {video_path.name} (job_id={job_id[:8]}...)")
            stats["enqueued"] += 1

        except Exception as e:
            print(f"  ✗ Failed to hash {video_path.name}: {e}")
            stats["failed_hash"] += 1
            continue

    return stats


def process_queue(
    db_path: str = "queue.db", n_workers: int = None, max_jobs: Optional[int] = None
) -> Dict[str, Any]:
    """Process jobs from the queue with parallel workers.

    This pulls jobs from the queue and processes them in parallel using
    a worker pool. Jobs are automatically retried on transient failures.

    Args:
        db_path: Path to SQLite database
        n_workers: Number of parallel workers (default: CPU count)
        max_jobs: Maximum number of jobs to process (default: all pending)

    Returns:
        Dictionary with processing statistics:
            - succeeded: Number of successful jobs
            - failed: Number of failed jobs
            - skipped: Number of jobs skipped (no content)
            - total_duration: Total processing time in seconds
    """
    manifest = SQLiteManifest(db_path)
    queue = SQLiteQueue(manifest)

    stats = {"succeeded": 0, "failed": 0, "skipped": 0, "total_duration": 0.0}

    print(f"\nProcessing queue with {n_workers or 'auto'} workers...")

    # Create worker pool
    with JobWorkerPool(n_workers=n_workers) as pool:
        processed = 0

        while True:
            # Check if we hit max_jobs limit
            if max_jobs and processed >= max_jobs:
                print(f"\nReached max_jobs limit ({max_jobs})")
                break

            # Dequeue next job
            worker_id = "worker-main"
            job = queue.dequeue(worker_id)

            if job is None:
                # No more jobs
                print("\nNo more jobs in queue")
                break

            print(f"\nProcessing: {Path(job.video_path).name} (job_id={job.job_id[:8]}...)")

            # Load config from job metadata
            config = job.metadata.get("config", {})
            output_dir = job.metadata.get("output_dir", "output")

            # Process in worker
            try:
                result = pool.submit(
                    process_video_job, job, config, db_path, Path(output_dir)
                ).result()

                # Update stats (status is already a string due to use_enum_values)
                status_str = (
                    result.status if isinstance(result.status, str) else result.status.value
                )
                if status_str == "succeeded":
                    stats["succeeded"] += 1
                    if not result.output_files:
                        stats["skipped"] += 1

                    print(f"  ✓ Success: {len(result.output_files)} clips rendered")

                elif status_str == "failed":
                    stats["failed"] += 1
                    print(f"  ✗ Failed: {result.error_message}")

                stats["total_duration"] += result.duration_s
                processed += 1

            except Exception as e:
                print(f"  ✗ Worker error: {e}")
                stats["failed"] += 1
                processed += 1
                continue

    return stats


def get_queue_stats(db_path: str = "queue.db") -> Dict[str, Any]:
    """Get current queue statistics.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dictionary with queue statistics:
            - pending: Number of pending jobs
            - in_progress: Number of jobs currently processing
            - succeeded: Number of successful jobs
            - failed: Number of failed jobs
            - total: Total jobs in queue
    """
    manifest = SQLiteManifest(db_path)
    queue = SQLiteQueue(manifest)

    # Get counts for each status
    all_jobs = queue.get_all_items()

    stats = {
        "pending": sum(1 for j in all_jobs if j.get("status") == "pending"),
        "in_progress": sum(1 for j in all_jobs if j.get("status") == "running"),
        "succeeded": sum(1 for j in all_jobs if j.get("status") == "succeeded"),
        "failed": sum(1 for j in all_jobs if j.get("status") == "failed"),
    }
    stats["total"] = len(all_jobs)

    return stats


def retry_failed(db_path: str = "queue.db") -> int:
    """Retry all failed jobs.

    Args:
        db_path: Path to SQLite database

    Returns:
        Number of jobs marked for retry
    """
    manifest = SQLiteManifest(db_path)
    queue = SQLiteQueue(manifest)

    # Get all failed jobs
    failed_jobs = queue.get_all_items(status_filter="failed")
    count = 0

    # Reset each failed job to pending
    for job in failed_jobs:
        try:
            # Update status to pending (reset for retry)
            manifest.db.conn.execute(
                """
                UPDATE job_items
                SET status = 'pending',
                    last_error = NULL,
                    attempt_count = 0
                WHERE job_id = ?
                """,
                (job["job_id"],),
            )
            manifest.db.conn.commit()
            count += 1
        except Exception as e:
            print(f"Failed to retry job {job['job_id']}: {e}")
            continue

    print(f"Marked {count} failed jobs for retry")
    return count


def clear_queue(db_path: str = "queue.db", clear_manifest: bool = False) -> None:
    """Clear all jobs from queue.

    Args:
        db_path: Path to SQLite database
        clear_manifest: If True, also clear the manifest cache
    """
    manifest = SQLiteManifest(db_path)

    # Clear queue
    manifest.db.conn.execute("DELETE FROM job_items")
    manifest.db.conn.commit()
    print("Queue cleared")

    # Optionally clear manifest (there's no separate manifest table, job_items contains everything)
    if clear_manifest:
        # Also clear state transitions
        manifest.db.conn.execute("DELETE FROM state_transitions")
        manifest.db.conn.commit()
        print("State transitions cleared")


def run_queued_scan(cli_args: Dict[str, Any]) -> None:
    """Queue-based version of run_scan.

    This is the main entry point for CLI 'process' command. It:
    1. Scans for videos (same as regular scan)
    2. Resolves config (same as regular scan)
    3. Enqueues jobs instead of processing directly
    4. Optionally starts workers to process the queue

    Args:
        cli_args: CLI arguments dictionary
    """
    # 1. Config
    conf = config_lib.resolve_config(cli_args)

    # 2. Output Setup
    output_base = cli_args.get("output", "output")

    # Use timestamped batch directory
    batch_name = datetime.now().strftime("batch_%Y%m%d_%H%M%S")
    batch_dir = Path(output_base) / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    print("--- 🚀 Starting Queued Pipeline ---")
    print(f"Batch directory: {batch_dir}")

    # 3. Scan
    input_path = cli_args.get("input")
    if not input_path:
        input_path = "."

    recursive = cli_args.get("recursive", False)
    limit = cli_args.get("limit", None)
    exts = cli_args.get("ext", None)

    if exts and isinstance(exts, str):
        exts = [e.strip() for e in exts.split(",")]

    print(f"\nScanning {input_path}...")
    video_files = scanner.scan_input(input_path, recursive=recursive, limit=limit, extensions=exts)
    print(f"Found {len(video_files)} videos.")

    if not video_files:
        print("No videos found. Exiting.")
        return

    # 4. Enqueue
    db_path = cli_args.get("db", "queue.db")
    force = cli_args.get("force", False)

    enqueue_stats = enqueue_batch(
        video_files=video_files,
        config=conf,
        output_dir=str(batch_dir),
        db_path=db_path,
        force=force,
    )

    print("\n" + "=" * 60)
    print("ENQUEUE SUMMARY")
    print("=" * 60)
    print(f"Total videos:         {enqueue_stats['total']}")
    print(f"Enqueued:             {enqueue_stats['enqueued']}")
    print(f"Cached (skipped):     {enqueue_stats['cached']}")
    print(f"Failed to hash:       {enqueue_stats['failed_hash']}")
    print("=" * 60)

    # 5. Optionally process queue
    if cli_args.get("no_process", False):
        print("\nJobs enqueued. Use 'content-ai queue process' to start processing.")
        return

    # Process queue
    n_workers = cli_args.get("workers", None)

    process_stats = process_queue(db_path=db_path, n_workers=n_workers)

    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Succeeded:            {process_stats['succeeded']}")
    print(f"Failed:               {process_stats['failed']}")
    print(f"Skipped (no clips):   {process_stats['skipped']}")
    print(f"Total duration:       {process_stats['total_duration']:.2f}s")
    print("=" * 60)

    # Save batch metadata
    # Convert config to dict if needed
    config_dict = conf
    if hasattr(conf, "model_dump"):
        config_dict = conf.model_dump()
    elif hasattr(conf, "dict"):
        config_dict = conf.dict()

    batch_meta = {
        "batch_name": batch_name,
        "timestamp": datetime.now().isoformat(),
        "config": config_dict,
        "enqueue_stats": enqueue_stats,
        "process_stats": process_stats,
        "cli_args": cli_args,
    }

    with open(batch_dir / "batch_meta.json", "w") as f:
        json.dump(batch_meta, f, indent=2)

    print(f"\nBatch complete. Results saved to: {batch_dir}")
