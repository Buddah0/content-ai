from __future__ import annotations

"""Abstract base classes for queue backends and manifest storage.

This module defines the interfaces for queue operations, manifest storage,
and worker pool management. These abstractions enable local-first implementations
(SQLite + ProcessPoolExecutor) while remaining distributed-ready for future
migration to Redis/Celery/Taskiq.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .models import JobItem, JobResult


class QueueBackend(ABC):
    """Abstract queue interface for local/distributed backends.

    Implementations must provide:
    - Thread-safe atomic dequeue operations
    - Idempotent enqueue (duplicate job_id doesn't corrupt state)
    - Crash recovery via reset_stale_running()
    - Heartbeat support for long-running jobs
    """

    @abstractmethod
    def enqueue(self, item: "JobItem") -> None:
        """Add item to queue (idempotent if job_id exists).

        Args:
            item: Job specification to enqueue

        Implementation notes:
        - Must be idempotent: enqueueing same job_id multiple times is safe
        - Should not overwrite items in 'running' or 'succeeded' states
        - Can update 'pending', 'failed', or 'dirty' items
        """
        pass

    @abstractmethod
    def dequeue(self, worker_id: str) -> Optional["JobItem"]:
        """Atomically pop next item and mark as running.

        Args:
            worker_id: Unique identifier for the claiming worker

        Returns:
            JobItem if queue has pending items, None if empty

        Implementation notes:
        - MUST be thread-safe (multiple workers calling concurrently)
        - MUST use atomic transaction (e.g., UPDATE...RETURNING)
        - Should respect priority (higher first) then FIFO order
        - Should set status='running', worker_id, started_at, last_heartbeat
        """
        pass

    @abstractmethod
    def ack_success(self, job_id: str, result: "JobResult") -> None:
        """Mark job as succeeded with validation data.

        Args:
            job_id: Job identifier
            result: Processing outcome with output files and hashes

        Implementation notes:
        - MUST validate output files exist before marking succeeded
        - MUST compute output hashes for integrity verification
        - Should atomically update state (all-or-nothing)
        - Should log state transition for audit trail
        """
        pass

    @abstractmethod
    def ack_fail(self, job_id: str, error: str, retry: bool) -> None:
        """Mark job as failed with optional retry.

        Args:
            job_id: Job identifier
            error: Error message (truncated to ~500 chars)
            retry: If True, re-enqueue with incremented attempt_count

        Implementation notes:
        - If retry=True and attempts < max_attempts: reset to 'pending'
        - If retry=False or attempts >= max_attempts: set to 'failed'
        - Should store last error for debugging
        - Should log state transition
        """
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Query job state (for status command).

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with job state fields or None if not found
        """
        pass

    @abstractmethod
    def reset_stale_running(self, timeout_s: int) -> int:
        """Crash recovery: Reset items stuck in 'running' state.

        Args:
            timeout_s: Consider job stale if no heartbeat in this duration

        Returns:
            Count of reset items

        Implementation notes:
        - Should check last_heartbeat timestamp (if supported)
        - Should handle jobs without heartbeat via started_at timeout
        - Should reset to 'pending' without incrementing attempt_count
        - This is called on pipeline startup for crash recovery
        """
        pass

    @abstractmethod
    def update_heartbeat(self, job_id: str) -> None:
        """Update heartbeat timestamp for long-running job.

        Args:
            job_id: Job identifier

        Implementation notes:
        - Called periodically by worker (e.g., every 60s)
        - Prevents job from being marked stale during long processing
        - Only updates if job is in 'running' state
        """
        pass

    @abstractmethod
    def get_all_items(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query items by status (for status command).

        Args:
            status_filter: Optional status to filter by (e.g., 'failed')

        Returns:
            List of job state dictionaries

        Implementation notes:
        - Can be O(n) - only used for status/repair commands
        - Should support filtering by status for efficiency
        """
        pass


class ManifestStore(ABC):
    """Abstract persistent state tracker for video processing runs.

    Responsibilities:
    - Store per-video processing state (pending, succeeded, failed, dirty)
    - Track input/config hashes for dirty detection
    - Validate output integrity via checksums
    - Provide O(log n) lookups by video_path
    """

    @abstractmethod
    def get_item_state(self, video_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve processing state for video file.

        Args:
            video_path: Absolute path to video file

        Returns:
            State dictionary or None if not in manifest

        Implementation notes:
        - Should use indexed lookup (O(log n))
        - State dict includes: job_id, status, hashes, timestamps, etc.
        """
        pass

    @abstractmethod
    def upsert_item(self, video_path: str, state: Dict[str, Any]) -> None:
        """Update or insert item state (atomic).

        Args:
            video_path: Absolute path to video file
            state: State dictionary to store

        Implementation notes:
        - Should be atomic (transaction)
        - video_path is unique constraint
        - Upsert based on job_id primary key
        """
        pass

    @abstractmethod
    def verify_hashes(
        self,
        video_path: str,
        config_hash: str,
        input_hashes: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check if item is dirty (config or input changed).

        Args:
            video_path: Absolute path to video file
            config_hash: SHA-256 of current resolved config
            input_hashes: Dict with 'quick_hash', 'full_hash', 'size'

        Returns:
            Tuple of (is_clean, reason_string)

        Implementation notes:
        - Should use tiered comparison for performance:
          1. Config hash check (fast)
          2. File size check (fast)
          3. Quick hash check (fast, 5 sample positions)
          4. Full hash check (slow but accurate, BLAKE2b)
        - Return (False, "reason") if dirty
        - Return (True, "reason") if clean
        """
        pass

    @abstractmethod
    def mark_dirty(self, video_path: str) -> None:
        """Mark item as needing re-run.

        Args:
            video_path: Absolute path to video file

        Implementation notes:
        - Sets status='dirty'
        - Should update timestamp
        """
        pass

    @abstractmethod
    def get_all_items(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query items by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of item state dictionaries
        """
        pass


class WorkerPool(ABC):
    """Abstract concurrency manager for parallel video processing.

    Implementations:
    - Local: ProcessPoolExecutor with worker initialization
    - Distributed: Celery/Taskiq with broker backend
    """

    @abstractmethod
    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """Submit task to worker pool.

        Args:
            fn: Callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future or task handle
        """
        pass

    @abstractmethod
    def map(self, fn: Callable, items: List[Any]) -> List[Any]:
        """Parallel map with progress tracking.

        Args:
            fn: Callable to apply to each item
            items: List of items to process

        Returns:
            List of results in order

        Implementation notes:
        - Should show progress bar (tqdm)
        - Should handle exceptions gracefully (continue processing)
        - Results should maintain input order
        """
        pass

    @abstractmethod
    def shutdown(self, wait: bool = True) -> None:
        """Graceful shutdown.

        Args:
            wait: If True, wait for pending tasks to complete
        """
        pass
