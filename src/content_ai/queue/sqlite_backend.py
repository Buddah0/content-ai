"""SQLite implementations of QueueBackend and ManifestStore.

This module provides the local-first, crash-safe queue implementation using:
- sqlite-utils for type-safe schema management
- WAL mode for better concurrent performance
- BEGIN IMMEDIATE transactions for atomic dequeue
- Exponential backoff retry for database lock handling
- Two-tier hashing for efficient dirty detection
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

try:
    from sqlite_utils import Database
except ImportError:
    raise ImportError(
        "sqlite-utils is required for queue functionality. "
        "Install it with: pip install sqlite-utils"
    )

from .backends import QueueBackend, ManifestStore
from .models import JobItem, JobResult, JobStatus, StateTransition
from .hashing import compute_output_hash


# SQLite schema SQL
SCHEMA_SQL = """
-- Job items table
CREATE TABLE IF NOT EXISTS job_items (
    job_id TEXT PRIMARY KEY,
    video_path TEXT UNIQUE NOT NULL,
    input_hash_quick TEXT NOT NULL,
    input_hash_full TEXT NOT NULL,
    input_size INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    last_heartbeat TEXT,
    worker_id TEXT,
    last_error TEXT,
    output_files TEXT,
    output_hashes TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_status ON job_items(status);
CREATE INDEX IF NOT EXISTS idx_priority_created ON job_items(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_video_path ON job_items(video_path);

-- State transition log (audit trail)
CREATE TABLE IF NOT EXISTS state_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    worker_id TEXT,
    error_snippet TEXT,
    FOREIGN KEY(job_id) REFERENCES job_items(job_id)
);

CREATE INDEX IF NOT EXISTS idx_transitions_job ON state_transitions(job_id, timestamp);

-- Run-level manifest
CREATE TABLE IF NOT EXISTS run_manifest (
    run_id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    total_items INTEGER DEFAULT 0,
    succeeded_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    pending_items INTEGER DEFAULT 0
);
"""


class SQLiteManifest(ManifestStore):
    """SQLite-based manifest store with ACID guarantees.

    Features:
    - WAL mode for better concurrent reads
    - Indexed lookups (O(log n))
    - Atomic upserts
    - Two-tier hash verification
    """

    def __init__(self, db_path: str):
        """Initialize manifest database.

        Args:
            db_path: Path to SQLite database file

        Creates schema if database doesn't exist.
        Enables WAL mode for concurrent performance.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = Database(str(self.db_path))

        # Enable WAL mode for better concurrent performance
        self.db.conn.execute("PRAGMA journal_mode=WAL")
        self.db.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still crash-safe
        self.db.conn.commit()

        # Create schema
        self._create_schema()

    def _create_schema(self):
        """Create tables and indexes if they don't exist."""
        self.db.executescript(SCHEMA_SQL)

    def get_item_state(self, video_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve processing state for video file.

        Args:
            video_path: Absolute path to video file

        Returns:
            State dictionary or None if not in manifest

        Complexity: O(log n) via video_path index
        """
        rows = list(self.db["job_items"].rows_where(
            "video_path = ?",
            [str(video_path)]
        ))

        if not rows:
            return None

        row = dict(rows[0])

        # Deserialize JSON fields
        if row.get('output_files'):
            row['output_files'] = json.loads(row['output_files'])
        else:
            row['output_files'] = []

        if row.get('output_hashes'):
            row['output_hashes'] = json.loads(row['output_hashes'])
        else:
            row['output_hashes'] = {}

        if row.get('metadata'):
            row['metadata'] = json.loads(row['metadata'])
        else:
            row['metadata'] = {}

        return row

    def upsert_item(self, video_path: str, state: Dict[str, Any]) -> None:
        """Update or insert item state (atomic).

        Args:
            video_path: Absolute path to video file
            state: State dictionary to store

        Transaction guarantees: Atomic update
        """
        # Serialize JSON fields
        state_copy = state.copy()

        if 'output_files' in state_copy and isinstance(state_copy['output_files'], list):
            state_copy['output_files'] = json.dumps(state_copy['output_files'])

        if 'output_hashes' in state_copy and isinstance(state_copy['output_hashes'], dict):
            state_copy['output_hashes'] = json.dumps(state_copy['output_hashes'])

        if 'metadata' in state_copy and isinstance(state_copy['metadata'], dict):
            state_copy['metadata'] = json.dumps(state_copy['metadata'])

        # Ensure video_path is set
        state_copy['video_path'] = str(video_path)

        # Use insert with replace=True for upsert behavior
        # This works better than upsert() for existing tables
        self.db["job_items"].insert(state_copy, pk="job_id", replace=True)

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

        Tiered comparison strategy:
        1. Config hash check (fast, O(1))
        2. File size check (fast, O(1))
        3. Quick hash check (fast, O(1))
        4. Full hash check (slow but accurate)
        """
        item = self.get_item_state(str(video_path))

        if not item:
            return False, "Item not in manifest"

        # Tier 0: Config hash check
        if item.get('config_hash') != config_hash:
            return False, "Config changed"

        # Tier 1: Size check (instant)
        if item.get('input_size') != input_hashes.get('size'):
            return False, "File size changed"

        # Tier 2: Quick hash check (instant)
        if item.get('input_hash_quick') == input_hashes.get('quick_hash'):
            # Quick hash matches - very likely unchanged
            return True, "Content unchanged (quick hash match)"

        # Tier 3: Full hash check (slow but accurate)
        if item.get('input_hash_full') != input_hashes.get('full_hash'):
            return False, "File content changed"

        # Quick hash changed but full hash same = metadata-only change
        # (e.g., file was touched, mtime updated, but content identical)
        return True, "Metadata changed, content unchanged"

    def mark_dirty(self, video_path: str) -> None:
        """Mark item as needing re-run.

        Args:
            video_path: Absolute path to video file

        Sets status='dirty' and updates timestamp.
        """
        with self.db.conn:
            self.db.execute("""
                UPDATE job_items
                SET status = ?, updated_at = ?
                WHERE video_path = ?
            """, (JobStatus.DIRTY.value, datetime.now().isoformat(), str(video_path)))

    def get_all_items(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query items by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of item state dictionaries

        Complexity: O(n) full scan (acceptable for status commands)
        """
        if status_filter:
            rows = self.db["job_items"].rows_where("status = ?", [status_filter])
        else:
            rows = self.db["job_items"].rows

        items = []
        for row in rows:
            item = dict(row)

            # Deserialize JSON fields
            if item.get('output_files'):
                item['output_files'] = json.loads(item['output_files'])
            else:
                item['output_files'] = []

            if item.get('output_hashes'):
                item['output_hashes'] = json.loads(item['output_hashes'])
            else:
                item['output_hashes'] = {}

            if item.get('metadata'):
                item['metadata'] = json.loads(item['metadata'])
            else:
                item['metadata'] = {}

            items.append(item)

        return items


class SQLiteQueue(QueueBackend):
    """SQLite-based queue with atomic dequeue operations.

    Features:
    - Atomic dequeue via UPDATE...RETURNING with BEGIN IMMEDIATE
    - Exponential backoff retry for database lock contention
    - Heartbeat support for long-running jobs
    - Automatic state transition logging
    - Crash recovery via reset_stale_running()

    Concurrency safety:
    - BEGIN IMMEDIATE ensures write lock from transaction start
    - Prevents race where multiple workers claim same job
    - Exponential backoff handles transient lock contention
    """

    def __init__(self, manifest: SQLiteManifest):
        """Initialize queue backend.

        Args:
            manifest: SQLiteManifest instance (shares same database)
        """
        self.manifest = manifest
        self.db = manifest.db

    def enqueue(self, item: JobItem) -> None:
        """Add item to queue (idempotent if job_id exists).

        Args:
            item: Job specification to enqueue

        Idempotency:
        - If job_id exists and status is 'succeeded' or 'running', no-op
        - If job_id exists and status is 'pending', 'failed', or 'dirty', update
        - If job_id doesn't exist, insert
        """
        existing = self.manifest.get_item_state(item.video_path)

        # Don't re-enqueue completed or running items
        if existing and existing.get('status') in (JobStatus.SUCCEEDED.value, JobStatus.RUNNING.value):
            return

        # Convert model to dict for storage
        state = {
            'job_id': item.job_id,
            'video_path': item.video_path,
            'input_hash_quick': item.input_hash_quick,
            'input_hash_full': item.input_hash_full,
            'input_size': item.input_size,
            'config_hash': item.config_hash,
            'status': item.status.value if isinstance(item.status, JobStatus) else item.status,
            'priority': item.priority,
            'attempt_count': item.attempt_count,
            'max_attempts': item.max_attempts,
            'created_at': item.created_at.isoformat() if isinstance(item.created_at, datetime) else item.created_at,
            'metadata': item.metadata,
        }

        self.manifest.upsert_item(item.video_path, state)

    def dequeue(self, worker_id: str) -> Optional[JobItem]:
        """Atomically pop next item and mark as running.

        Args:
            worker_id: Unique identifier for the claiming worker

        Returns:
            JobItem if queue has pending items, None if empty

        Atomicity: Uses BEGIN IMMEDIATE + UPDATE...RETURNING
        Retry logic: Exponential backoff on database lock
        """
        return self._dequeue_with_retry(worker_id, max_retries=3)

    def _dequeue_with_retry(self, worker_id: str, max_retries: int = 3) -> Optional[JobItem]:
        """Dequeue with exponential backoff on SQLITE_BUSY.

        Args:
            worker_id: Worker identifier
            max_retries: Max retry attempts on lock contention

        Returns:
            JobItem or None

        Implementation note:
        - BEGIN IMMEDIATE ensures write lock from transaction start
        - This prevents race where multiple workers claim same job
        - Exponential backoff: 100ms, 200ms, 400ms delays
        """
        for attempt in range(max_retries):
            try:
                with self.db.conn:
                    # CRITICAL: BEGIN IMMEDIATE ensures write lock immediately
                    # Without this, multiple workers can select same job before update
                    self.db.conn.execute("BEGIN IMMEDIATE")

                    try:
                        now = datetime.now().isoformat()

                        cursor = self.db.conn.execute("""
                            UPDATE job_items
                            SET status = ?,
                                worker_id = ?,
                                started_at = ?,
                                last_heartbeat = ?
                            WHERE job_id = (
                                SELECT job_id FROM job_items
                                WHERE status = ?
                                ORDER BY priority DESC, created_at ASC
                                LIMIT 1
                            )
                            RETURNING *
                        """, (
                            JobStatus.RUNNING.value,
                            worker_id,
                            now,
                            now,
                            JobStatus.PENDING.value
                        ))

                        row = cursor.fetchone()
                        self.db.conn.commit()

                        if row:
                            # Log state transition
                            self._log_transition(
                                job_id=row[0],  # job_id is first column
                                from_state=JobStatus.PENDING.value,
                                to_state=JobStatus.RUNNING.value,
                                worker_id=worker_id
                            )

                            # Convert row to JobItem
                            return self._row_to_job_item(row)

                        return None

                    except Exception:
                        self.db.conn.rollback()
                        raise

            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "database is locked" in error_msg and attempt < max_retries - 1:
                    # Exponential backoff: 100ms, 200ms, 400ms
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                raise

        return None

    def _row_to_job_item(self, row) -> JobItem:
        """Convert SQLite row to JobItem model.

        Args:
            row: SQLite row tuple

        Returns:
            JobItem instance
        """
        # Row columns match job_items table schema (20 columns with updated_at)
        (job_id, video_path, input_hash_quick, input_hash_full, input_size,
         config_hash, status, priority, attempt_count, max_attempts,
         created_at, updated_at, started_at, completed_at, last_heartbeat, worker_id,
         last_error, output_files, output_hashes, metadata) = row

        return JobItem(
            job_id=job_id,
            video_path=video_path,
            input_hash_quick=input_hash_quick,
            input_hash_full=input_hash_full,
            input_size=input_size,
            config_hash=config_hash,
            status=JobStatus(status),
            priority=priority,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            created_at=datetime.fromisoformat(created_at),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
            last_heartbeat=datetime.fromisoformat(last_heartbeat) if last_heartbeat else None,
            worker_id=worker_id,
            last_error=last_error,
            output_files=json.loads(output_files) if output_files else [],
            output_hashes=json.loads(output_hashes) if output_hashes else {},
            metadata=json.loads(metadata) if metadata else {}
        )

    def ack_success(self, job_id: str, result: JobResult) -> None:
        """Mark job as succeeded with validation data.

        Args:
            job_id: Job identifier
            result: Processing outcome with output files

        Validation:
        - Verifies all output files exist
        - Computes output hashes for integrity
        - Atomically updates state (all-or-nothing)

        Raises:
            ValueError: If output files missing or validation fails
        """
        # Validate output files exist
        for output_file in result.output_files:
            if not Path(output_file).exists():
                raise ValueError(f"Output file missing: {output_file}")

        # Compute output hashes
        output_hashes = {}
        for output_file in result.output_files:
            try:
                output_hashes[output_file] = compute_output_hash(output_file)
            except Exception as e:
                raise ValueError(f"Failed to hash output {output_file}: {e}")

        # Atomic state update
        with self.db.conn:
            self.db.execute("""
                UPDATE job_items
                SET status = ?,
                    completed_at = ?,
                    output_files = ?,
                    output_hashes = ?
                WHERE job_id = ?
            """, (
                JobStatus.SUCCEEDED.value,
                datetime.now().isoformat(),
                json.dumps(result.output_files),
                json.dumps(output_hashes),
                job_id
            ))

            self._log_transition(
                job_id=job_id,
                from_state=JobStatus.RUNNING.value,
                to_state=JobStatus.SUCCEEDED.value,
                worker_id=None
            )

    def ack_fail(self, job_id: str, error: str, retry: bool) -> None:
        """Mark job as failed with optional retry.

        Args:
            job_id: Job identifier
            error: Error message (truncated to 500 chars)
            retry: If True, re-enqueue with incremented attempt_count

        Retry logic:
        - If retry=True and attempts < max_attempts: reset to 'pending'
        - Otherwise: set to 'failed' (terminal state)
        """
        item = self.manifest.get_item_state(self.get_status(job_id)['video_path'])
        new_attempt = item['attempt_count'] + 1

        # Truncate error message
        error_snippet = error[:500] if error else None

        with self.db.conn:
            if retry and new_attempt < item['max_attempts']:
                # Retry: reset to pending
                self.db.execute("""
                    UPDATE job_items
                    SET status = ?,
                        attempt_count = ?,
                        last_error = ?,
                        worker_id = NULL
                    WHERE job_id = ?
                """, (
                    JobStatus.PENDING.value,
                    new_attempt,
                    error_snippet,
                    job_id
                ))

                self._log_transition(
                    job_id=job_id,
                    from_state=JobStatus.RUNNING.value,
                    to_state=JobStatus.PENDING.value,
                    worker_id=None,
                    error=error_snippet
                )
            else:
                # Failed: terminal state
                self.db.execute("""
                    UPDATE job_items
                    SET status = ?,
                        completed_at = ?,
                        attempt_count = ?,
                        last_error = ?
                    WHERE job_id = ?
                """, (
                    JobStatus.FAILED.value,
                    datetime.now().isoformat(),
                    new_attempt,
                    error_snippet,
                    job_id
                ))

                self._log_transition(
                    job_id=job_id,
                    from_state=JobStatus.RUNNING.value,
                    to_state=JobStatus.FAILED.value,
                    worker_id=None,
                    error=error_snippet
                )

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Query job state.

        Args:
            job_id: Job identifier

        Returns:
            State dictionary or empty dict if not found
        """
        rows = list(self.db["job_items"].rows_where("job_id = ?", [job_id]))
        if not rows:
            return {}

        row = dict(rows[0])

        # Deserialize JSON fields
        if row.get('output_files'):
            row['output_files'] = json.loads(row['output_files'])
        if row.get('output_hashes'):
            row['output_hashes'] = json.loads(row['output_hashes'])
        if row.get('metadata'):
            row['metadata'] = json.loads(row['metadata'])

        return row

    def reset_stale_running(self, timeout_s: int = 7200) -> int:
        """Crash recovery: Reset items stuck in 'running' state.

        Args:
            timeout_s: Consider job stale if no heartbeat in this duration
                      Default: 7200s (2 hours) for long 4K video processing

        Returns:
            Count of reset items

        Logic:
        - Job is stale if:
          1. No heartbeat in 10 minutes (indicates worker crash)
          2. OR started > timeout_s ago AND no heartbeat (long job timeout)

        Implementation:
        - Resets to 'pending' without incrementing attempt_count
        - Clears worker_id
        - Logs transition for audit
        """
        cutoff_heartbeat = datetime.now() - timedelta(seconds=600)  # 10 minutes
        cutoff_started = datetime.now() - timedelta(seconds=timeout_s)

        with self.db.conn:
            cursor = self.db.execute("""
                UPDATE job_items
                SET status = ?, worker_id = NULL
                WHERE status = ?
                  AND (
                      last_heartbeat < ?
                      OR (started_at < ? AND last_heartbeat IS NULL)
                  )
                RETURNING job_id
            """, (
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
                cutoff_heartbeat.isoformat(),
                cutoff_started.isoformat()
            ))

            rows = cursor.fetchall()

            # Log transitions
            for row in rows:
                self._log_transition(
                    job_id=row[0],
                    from_state=JobStatus.RUNNING.value,
                    to_state=JobStatus.PENDING.value,
                    worker_id=None,
                    error="Reset stale job (crash recovery)"
                )

            return len(rows)

    def update_heartbeat(self, job_id: str) -> None:
        """Update heartbeat timestamp for long-running job.

        Args:
            job_id: Job identifier

        Only updates if job is in 'running' state.
        Called periodically by worker (e.g., every 60s).
        """
        with self.db.conn:
            self.db.execute("""
                UPDATE job_items
                SET last_heartbeat = ?
                WHERE job_id = ? AND status = ?
            """, (
                datetime.now().isoformat(),
                job_id,
                JobStatus.RUNNING.value
            ))

    def get_all_items(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query items by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of job state dictionaries
        """
        return self.manifest.get_all_items(status_filter)

    def _log_transition(
        self,
        job_id: str,
        from_state: str,
        to_state: str,
        worker_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log state transition to audit trail.

        Args:
            job_id: Job identifier
            from_state: Previous state
            to_state: New state
            worker_id: Worker that caused transition
            error: Error message if applicable
        """
        self.db["state_transitions"].insert({
            "job_id": job_id,
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": datetime.now().isoformat(),
            "worker_id": worker_id,
            "error_snippet": error[:200] if error else None,
        })
