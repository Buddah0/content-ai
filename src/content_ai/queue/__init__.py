"""Job queue and manifest system for resumable processing."""

from .backends import ManifestStore, QueueBackend, WorkerPool
from .hashing import compute_config_hash, compute_input_hash, compute_output_hash
from .models import JobItem, JobResult, JobStatus
from .sqlite_backend import SQLiteManifest, SQLiteQueue
from .worker import JobWorkerPool, process_video_job

__all__ = [
    "QueueBackend",
    "ManifestStore",
    "WorkerPool",
    "JobItem",
    "JobResult",
    "JobStatus",
    "SQLiteQueue",
    "SQLiteManifest",
    "compute_input_hash",
    "compute_config_hash",
    "compute_output_hash",
    "JobWorkerPool",
    "process_video_job",
]
