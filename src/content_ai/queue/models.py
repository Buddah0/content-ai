"""Pydantic models for job queue data structures.

This module defines the type-safe models used throughout the queue system.
All models use Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing states with explicit semantics.

    State transitions:
        pending → running     (worker dequeues)
        running → succeeded   (processing completes + validation)
        running → failed      (max retries exhausted)
        running → pending     (crash recovery or retry)
        succeeded → dirty     (config/input changed)
        dirty → running       (re-run triggered)
        failed → running      (manual retry via --retry-failed)
        * → skipped           (user filter excludes item)
    """

    PENDING = "pending"  # Queued but not started
    RUNNING = "running"  # Currently being processed
    SUCCEEDED = "succeeded"  # Completed successfully (outputs validated)
    FAILED = "failed"  # Failed after max retry attempts
    DIRTY = "dirty"  # Succeeded but needs re-run (config/input changed)
    SKIPPED = "skipped"  # Intentionally excluded (e.g., file too small)


class JobItem(BaseModel):
    """Immutable job specification for queue operations.

    This model represents a single video processing job with all metadata
    needed for execution, retry logic, and dirty detection.
    """

    job_id: str = Field(..., description="Unique job identifier (UUID)")
    video_path: str = Field(..., description="Absolute path to video file")
    input_hash_quick: str = Field(..., description="Quick hash (size + 5 samples)")
    input_hash_full: str = Field(..., description="Full content hash (BLAKE2b)")
    input_size: int = Field(..., description="File size in bytes", ge=0)
    config_hash: str = Field(..., description="SHA-256 of resolved config JSON")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current job state")
    priority: int = Field(default=0, ge=0, description="Higher = processed first")
    attempt_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_attempts: int = Field(default=3, ge=1, description="Max retry limit")
    created_at: datetime = Field(default_factory=datetime.now, description="Queue time")
    started_at: Optional[datetime] = Field(default=None, description="Processing start time")
    completed_at: Optional[datetime] = Field(default=None, description="Completion time")
    last_heartbeat: Optional[datetime] = Field(
        default=None, description="Last heartbeat for long jobs"
    )
    worker_id: Optional[str] = Field(default=None, description="Worker that claimed job")
    last_error: Optional[str] = Field(default=None, description="Last error message (truncated)")
    output_files: List[str] = Field(default_factory=list, description="Rendered clip paths")
    output_hashes: Dict[str, str] = Field(
        default_factory=dict, description="Output file SHA-256 map"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="User-defined tags")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True  # Serialize enums as strings


class JobResult(BaseModel):
    """Processing outcome returned by worker.

    This model captures the result of job execution, including success/failure
    status, output files, errors, and timing information.
    """

    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Final status (succeeded or failed)")
    output_files: List[str] = Field(default_factory=list, description="Generated clip paths")
    error_message: Optional[str] = Field(default=None, description="Error details if failed")
    duration_s: float = Field(default=0.0, ge=0.0, description="Processing time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional result metadata")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class RunManifest(BaseModel):
    """Run-level metadata for tracking batch processing state.

    This model stores aggregate statistics and configuration for an entire
    processing run (e.g., run_001, run_002).
    """

    run_id: str = Field(..., description="Run identifier (e.g., run_001)")
    config_hash: str = Field(..., description="Config fingerprint for this run")
    created_at: datetime = Field(default_factory=datetime.now, description="Run start time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    status: str = Field(
        default="in_progress", description="Run status: in_progress, completed, failed"
    )
    total_items: int = Field(default=0, ge=0, description="Total jobs in run")
    succeeded_items: int = Field(default=0, ge=0, description="Successfully completed jobs")
    failed_items: int = Field(default=0, ge=0, description="Failed jobs")
    pending_items: int = Field(default=0, ge=0, description="Not yet processed jobs")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class StateTransition(BaseModel):
    """Audit log entry for job state changes.

    Tracks all state transitions for debugging and compliance.
    """

    id: Optional[int] = Field(default=None, description="Auto-increment ID")
    job_id: str = Field(..., description="Job identifier")
    from_state: Optional[str] = Field(default=None, description="Previous state")
    to_state: str = Field(..., description="New state")
    timestamp: datetime = Field(default_factory=datetime.now, description="Transition time")
    worker_id: Optional[str] = Field(default=None, description="Worker that caused transition")
    error_snippet: Optional[str] = Field(default=None, description="First 200 chars of error")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
