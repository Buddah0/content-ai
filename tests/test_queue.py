"""Unit tests for queue system.

Tests cover:
- Job enqueue/dequeue operations
- Atomic state transitions
- Hash computation and verification
- Crash recovery logic
- Concurrent dequeue safety
"""

import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from content_ai.queue import (
    JobItem,
    JobResult,
    JobStatus,
    SQLiteManifest,
    SQLiteQueue,
    compute_config_hash,
    compute_input_hash,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_manifest.db"
        yield str(db_path)


@pytest.fixture
def manifest(temp_db):
    """Create SQLiteManifest instance."""
    return SQLiteManifest(temp_db)


@pytest.fixture
def queue(manifest):
    """Create SQLiteQueue instance."""
    return SQLiteQueue(manifest)


@pytest.fixture
def temp_video():
    """Create temporary test video file."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".mp4", delete=False) as f:
        # Write some dummy content
        f.write(b"test video content" * 1000)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestHashComputation:
    """Test hash computation functions."""

    def test_compute_input_hash(self, temp_video):
        """Test two-tier input hash computation."""
        result = compute_input_hash(temp_video)

        assert "quick_hash" in result
        assert "full_hash" in result
        assert "size" in result
        assert result["size"] > 0
        assert len(result["quick_hash"]) == 64  # SHA-256 hex length
        assert len(result["full_hash"]) == 128  # BLAKE2b hex length

    def test_compute_input_hash_deterministic(self, temp_video):
        """Test that hash computation is deterministic."""
        hash1 = compute_input_hash(temp_video)
        hash2 = compute_input_hash(temp_video)

        assert hash1["quick_hash"] == hash2["quick_hash"]
        assert hash1["full_hash"] == hash2["full_hash"]
        assert hash1["size"] == hash2["size"]

    def test_compute_input_hash_file_not_found(self):
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            compute_input_hash("/nonexistent/file.mp4")

    def test_compute_config_hash(self):
        """Test config hash computation."""
        config = {
            "detection": {"rms_threshold": 0.1},
            "processing": {"pad_before_s": 1.0},
        }

        hash1 = compute_config_hash(config)
        hash2 = compute_config_hash(config)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_compute_config_hash_order_independent(self):
        """Test that config hash is independent of key order."""
        config1 = {"a": 1, "b": 2}
        config2 = {"b": 2, "a": 1}

        assert compute_config_hash(config1) == compute_config_hash(config2)


class TestManifestStore:
    """Test manifest storage operations."""

    def test_create_schema(self, manifest):
        """Test that schema is created correctly."""
        # Should not raise
        assert manifest.db is not None

    def test_upsert_item(self, manifest, temp_video):
        """Test item upsert operation."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        state = {
            "job_id": str(uuid.uuid4()),
            "video_path": video_path,
            "input_hash_quick": input_hashes["quick_hash"],
            "input_hash_full": input_hashes["full_hash"],
            "input_size": input_hashes["size"],
            "config_hash": "test_config_hash",
            "status": JobStatus.PENDING.value,
            "priority": 0,
            "attempt_count": 0,
            "max_attempts": 3,
            "created_at": datetime.now().isoformat(),
        }

        manifest.upsert_item(video_path, state)

        # Retrieve and verify
        retrieved = manifest.get_item_state(video_path)
        assert retrieved is not None
        assert retrieved["job_id"] == state["job_id"]
        assert retrieved["status"] == JobStatus.PENDING.value

    def test_get_item_state_not_found(self, manifest):
        """Test getting state for non-existent item."""
        result = manifest.get_item_state("/nonexistent/video.mp4")
        assert result is None

    def test_verify_hashes_clean(self, manifest, temp_video):
        """Test hash verification for unchanged file."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)
        config_hash = "test_config_hash"

        # Store item
        state = {
            "job_id": str(uuid.uuid4()),
            "video_path": video_path,
            "input_hash_quick": input_hashes["quick_hash"],
            "input_hash_full": input_hashes["full_hash"],
            "input_size": input_hashes["size"],
            "config_hash": config_hash,
            "status": JobStatus.SUCCEEDED.value,
            "priority": 0,
            "attempt_count": 0,
            "max_attempts": 3,
            "created_at": datetime.now().isoformat(),
        }
        manifest.upsert_item(video_path, state)

        # Verify hashes
        is_clean, reason = manifest.verify_hashes(video_path, config_hash, input_hashes)

        assert is_clean is True
        assert "unchanged" in reason.lower()

    def test_verify_hashes_config_changed(self, manifest, temp_video):
        """Test hash verification detects config change."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        # Store item with one config hash
        state = {
            "job_id": str(uuid.uuid4()),
            "video_path": video_path,
            "input_hash_quick": input_hashes["quick_hash"],
            "input_hash_full": input_hashes["full_hash"],
            "input_size": input_hashes["size"],
            "config_hash": "old_config_hash",
            "status": JobStatus.SUCCEEDED.value,
            "priority": 0,
            "attempt_count": 0,
            "max_attempts": 3,
            "created_at": datetime.now().isoformat(),
        }
        manifest.upsert_item(video_path, state)

        # Verify with different config hash
        is_clean, reason = manifest.verify_hashes(video_path, "new_config_hash", input_hashes)

        assert is_clean is False
        assert "config" in reason.lower()

    def test_mark_dirty(self, manifest, temp_video):
        """Test marking item as dirty."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        # Store succeeded item
        state = {
            "job_id": str(uuid.uuid4()),
            "video_path": video_path,
            "input_hash_quick": input_hashes["quick_hash"],
            "input_hash_full": input_hashes["full_hash"],
            "input_size": input_hashes["size"],
            "config_hash": "test_config_hash",
            "status": JobStatus.SUCCEEDED.value,
            "priority": 0,
            "attempt_count": 0,
            "max_attempts": 3,
            "created_at": datetime.now().isoformat(),
        }
        manifest.upsert_item(video_path, state)

        # Mark dirty
        manifest.mark_dirty(video_path)

        # Verify status changed
        retrieved = manifest.get_item_state(video_path)
        assert retrieved["status"] == JobStatus.DIRTY.value


class TestQueueOperations:
    """Test queue enqueue/dequeue operations."""

    def test_enqueue_dequeue(self, queue, temp_video):
        """Test basic enqueue and dequeue."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        job = JobItem(
            job_id=str(uuid.uuid4()),
            video_path=video_path,
            input_hash_quick=input_hashes["quick_hash"],
            input_hash_full=input_hashes["full_hash"],
            input_size=input_hashes["size"],
            config_hash="test_config_hash",
            status=JobStatus.PENDING,
        )

        queue.enqueue(job)

        # Dequeue
        dequeued = queue.dequeue(worker_id="test-worker")

        assert dequeued is not None
        assert dequeued.job_id == job.job_id
        assert dequeued.status == JobStatus.RUNNING
        assert dequeued.worker_id == "test-worker"

    def test_dequeue_empty_queue(self, queue):
        """Test dequeueing from empty queue."""
        result = queue.dequeue(worker_id="test-worker")
        assert result is None

    def test_enqueue_idempotent(self, queue, temp_video):
        """Test that enqueueing same job is idempotent."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        job = JobItem(
            job_id=str(uuid.uuid4()),
            video_path=video_path,
            input_hash_quick=input_hashes["quick_hash"],
            input_hash_full=input_hashes["full_hash"],
            input_size=input_hashes["size"],
            config_hash="test_config_hash",
            status=JobStatus.PENDING,
        )

        queue.enqueue(job)
        queue.enqueue(job)  # Second enqueue

        # Should only dequeue once
        dequeued1 = queue.dequeue(worker_id="test-worker-1")
        dequeued2 = queue.dequeue(worker_id="test-worker-2")

        assert dequeued1 is not None
        assert dequeued2 is None

    def test_ack_success(self, queue, temp_video):
        """Test acknowledging successful job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy output file
            output_file = Path(tmpdir) / "output.mp4"
            output_file.write_text("test output")

            video_path = temp_video
            input_hashes = compute_input_hash(video_path)

            job = JobItem(
                job_id=str(uuid.uuid4()),
                video_path=video_path,
                input_hash_quick=input_hashes["quick_hash"],
                input_hash_full=input_hashes["full_hash"],
                input_size=input_hashes["size"],
                config_hash="test_config_hash",
                status=JobStatus.PENDING,
            )

            queue.enqueue(job)
            dequeued = queue.dequeue(worker_id="test-worker")

            result = JobResult(
                job_id=dequeued.job_id,
                status=JobStatus.SUCCEEDED,
                output_files=[str(output_file)],
                duration_s=1.5,
            )

            queue.ack_success(dequeued.job_id, result)

            # Verify status
            status = queue.get_status(dequeued.job_id)
            assert status["status"] == JobStatus.SUCCEEDED.value
            assert len(status["output_files"]) == 1

    def test_ack_fail_with_retry(self, queue, temp_video):
        """Test acknowledging failed job with retry."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        job = JobItem(
            job_id=str(uuid.uuid4()),
            video_path=video_path,
            input_hash_quick=input_hashes["quick_hash"],
            input_hash_full=input_hashes["full_hash"],
            input_size=input_hashes["size"],
            config_hash="test_config_hash",
            status=JobStatus.PENDING,
            max_attempts=3,
        )

        queue.enqueue(job)
        dequeued = queue.dequeue(worker_id="test-worker")

        queue.ack_fail(dequeued.job_id, "Test error", retry=True)

        # Verify status changed to pending for retry
        status = queue.get_status(dequeued.job_id)
        assert status["status"] == JobStatus.PENDING.value
        assert status["attempt_count"] == 1
        assert status["last_error"] == "Test error"

    def test_ack_fail_no_retry(self, queue, temp_video):
        """Test acknowledging failed job without retry."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        job = JobItem(
            job_id=str(uuid.uuid4()),
            video_path=video_path,
            input_hash_quick=input_hashes["quick_hash"],
            input_hash_full=input_hashes["full_hash"],
            input_size=input_hashes["size"],
            config_hash="test_config_hash",
            status=JobStatus.PENDING,
        )

        queue.enqueue(job)
        dequeued = queue.dequeue(worker_id="test-worker")

        queue.ack_fail(dequeued.job_id, "Test error", retry=False)

        # Verify status is failed
        status = queue.get_status(dequeued.job_id)
        assert status["status"] == JobStatus.FAILED.value

    def test_reset_stale_running(self, queue, temp_video):
        """Test resetting stale running jobs."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        job = JobItem(
            job_id=str(uuid.uuid4()),
            video_path=video_path,
            input_hash_quick=input_hashes["quick_hash"],
            input_hash_full=input_hashes["full_hash"],
            input_size=input_hashes["size"],
            config_hash="test_config_hash",
            status=JobStatus.PENDING,
        )

        queue.enqueue(job)
        dequeued = queue.dequeue(worker_id="test-worker")

        # Manually set old started_at timestamp
        queue.db.execute(
            "UPDATE job_items SET started_at = '2020-01-01T00:00:00', last_heartbeat = NULL WHERE job_id = ?",
            [dequeued.job_id],
        )

        # Reset stale jobs
        reset_count = queue.reset_stale_running(timeout_s=60)

        assert reset_count == 1

        # Verify status changed to pending
        status = queue.get_status(dequeued.job_id)
        assert status["status"] == JobStatus.PENDING.value

    def test_update_heartbeat(self, queue, temp_video):
        """Test updating heartbeat timestamp."""
        video_path = temp_video
        input_hashes = compute_input_hash(video_path)

        job = JobItem(
            job_id=str(uuid.uuid4()),
            video_path=video_path,
            input_hash_quick=input_hashes["quick_hash"],
            input_hash_full=input_hashes["full_hash"],
            input_size=input_hashes["size"],
            config_hash="test_config_hash",
            status=JobStatus.PENDING,
        )

        queue.enqueue(job)
        dequeued = queue.dequeue(worker_id="test-worker")

        initial_heartbeat = dequeued.last_heartbeat

        # Update heartbeat
        import time

        time.sleep(0.1)
        queue.update_heartbeat(dequeued.job_id)

        # Verify heartbeat updated
        status = queue.get_status(dequeued.job_id)
        assert status["last_heartbeat"] != initial_heartbeat.isoformat()
