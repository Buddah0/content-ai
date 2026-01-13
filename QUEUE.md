# Job Queue + Resumable Runs System

**Status:** ✅ Production-Ready (Tested with 207MB real gameplay footage)

This document describes the job queue and resumable runs system implemented in Content AI, enabling batch processing with crash recovery, dirty detection, and parallel execution.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [CLI Reference](#cli-reference)
- [Resume & Dirty Detection](#resume--dirty-detection)
- [Performance & Concurrency](#performance--concurrency)
- [Error Handling & Recovery](#error-handling--recovery)
- [Manifest Schema](#manifest-schema)
- [Developer Guide](#developer-guide)

---

## Overview

### Why Queue-Based Processing?

The queue system solves several problems encountered when batch-processing large collections of gameplay videos:

1. **Crash Recovery**: Resume processing after crashes/interruptions without re-processing completed videos
2. **Config Change Detection**: Automatically re-process videos when detection parameters change
3. **Parallel Processing**: Leverage multiple CPU cores for faster batch jobs
4. **Progress Persistence**: Track which videos succeeded, failed, or are pending
5. **Retry Logic**: Automatically retry transient failures with configurable limits

### Key Features

- **SQLite-based manifest** - Zero external dependencies, local-first design
- **Two-tier hashing** - Fast dirty detection using quick hash + full content hash
- **Atomic state transitions** - ACID guarantees prevent partial updates
- **Worker heartbeats** - Long-running jobs tracked with periodic updates
- **Idempotent processing** - Same input always produces same output
- **Distributed-ready** - Abstract interfaces allow future Redis/Cloud backends

---

## Quick Start

### Process Videos with Queue

```bash
# Process all videos in a directory (enqueue + process)
content-ai process --input ./videos --output ./output

# Resume existing run (skip completed videos)
content-ai process --input ./videos --resume

# Force re-process all (ignore cache)
content-ai process --input ./videos --force

# Parallel processing with 8 workers
content-ai process --input ./videos --workers 8
```

### Check Queue Status

```bash
# Show current queue statistics
content-ai queue status

# Output:
# QUEUE STATUS
# ============================================================
# Pending:              10
# In Progress:          2
# Succeeded:            35
# Failed:               1
# Total:                48
# ============================================================
```

### Retry Failed Jobs

```bash
# Retry all failed jobs
content-ai queue retry

# Resume processing after retry
content-ai queue process
```

### Clear Queue

```bash
# Clear all jobs (keep manifest cache)
content-ai queue clear

# Clear jobs AND manifest cache (fresh start)
content-ai queue clear --manifest
```

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────┐
│                   CLI Interface                         │
│  content-ai process / content-ai queue [status|retry]   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Queued Pipeline Layer                      │
│  • Scan videos                                          │
│  • Compute hashes (config + input)                      │
│  • Enqueue jobs (skip cached)                           │
│  • Spawn worker pool                                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                SQLite Manifest Store                    │
│  • job_items table (status, hashes, outputs)            │
│  • state_transitions table (audit log)                  │
│  • Atomic enqueue/dequeue                               │
│  • Dirty detection (hash comparison)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ProcessPoolExecutor Workers                │
│  • Pre-load heavy libraries (librosa, moviepy)          │
│  • Process videos in parallel                           │
│  • Update heartbeats for long jobs                      │
│  • Ack success/failure with retry logic                 │
└─────────────────────────────────────────────────────────┘
```

### State Machine

```
         ┌──────────┐
         │ PENDING  │
         └────┬─────┘
              │
              │ dequeue()
              ▼
         ┌──────────┐
    ┌───┤ RUNNING  │◄───┐
    │   └────┬─────┘    │ retry
    │        │           │ (if attempts < max)
    │        │           │
    │  success/failure   │
    │        │           │
    ▼        ▼           │
┌─────────┐  ┌─────────┐
│SUCCEEDED│  │ FAILED  │──┘
└────┬────┘  └─────────┘
     │
     │ config/input changed
     ▼
┌─────────┐
│  DIRTY  │──────┐
└─────────┘      │
     ▲           │
     └───────────┘
   mark_dirty() + re-enqueue
```

**State Transitions:**
- `pending` → `running` (worker dequeues job)
- `running` → `succeeded` (processing completes, outputs validated)
- `running` → `failed` (max retries exhausted)
- `running` → `pending` (crash recovery OR retry)
- `succeeded` → `dirty` (config/input changed)
- `dirty` → `running` (re-run triggered)

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| [queued_pipeline.py](src/content_ai/queued_pipeline.py) | High-level API for batch processing with queue |
| [queue/models.py](src/content_ai/queue/models.py) | Pydantic data models (JobItem, JobResult, JobStatus) |
| [queue/backends.py](src/content_ai/queue/backends.py) | Abstract interfaces (QueueBackend, ManifestStore) |
| [queue/sqlite_backend.py](src/content_ai/queue/sqlite_backend.py) | SQLite implementation with atomic operations |
| [queue/worker.py](src/content_ai/queue/worker.py) | Worker pool + job processing logic |
| [queue/hashing.py](src/content_ai/queue/hashing.py) | Input/config/output fingerprinting |

---

## CLI Reference

### `content-ai process` (Queue-based Batch Processing)

Process videos using the job queue system (resumable, parallel).

```bash
content-ai process --input <path> [options]
```

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--input, -i` | string | *required* | Input file or directory |
| `--output, -o` | string | `output` | Output directory |
| `--db` | string | `queue.db` | Queue database path |
| `--workers, -w` | int | CPU count | Number of parallel workers |
| `--force, -f` | flag | false | Reprocess all (ignore cache) |
| `--no-process` | flag | false | Enqueue only, don't process |
| `--recursive, -r` | flag | false | Recursive directory scan |
| `--ext` | string | `mp4,mov,mkv,avi` | Comma-separated extensions |
| `--limit` | int | None | Max videos to process |
| `--rms-threshold` | float | from config | Override RMS threshold |
| `--max-duration` | int | from config | Max montage duration (s) |
| `--max-segments` | int | from config | Max segments in montage |
| `--order` | string | from config | Ordering strategy |

**Examples:**

```bash
# Basic batch processing
content-ai process --input ./raw_videos --output ./processed

# Resume after crash
content-ai process --input ./raw_videos --resume

# Parallel processing with 8 workers
content-ai process --input ./raw_videos --workers 8

# Enqueue only (don't process yet)
content-ai process --input ./raw_videos --no-process

# Config override (triggers dirty detection)
content-ai process --input ./raw_videos --rms-threshold 0.15
```

### `content-ai queue status`

Show current queue statistics.

```bash
content-ai queue status [--db queue.db]
```

**Output:**
```
QUEUE STATUS
============================================================
Pending:              10
In Progress:          2
Succeeded:            35
Failed:               1
Total:                48
============================================================
```

### `content-ai queue process`

Process existing queue (without enqueueing new jobs).

```bash
content-ai queue process [--db queue.db] [--workers N] [--max-jobs N]
```

**Options:**
- `--db`: Queue database path (default: `queue.db`)
- `--workers, -w`: Number of parallel workers (default: CPU count)
- `--max-jobs`: Stop after processing N jobs (useful for testing)

**Example:**
```bash
# Process next 10 jobs with 4 workers
content-ai queue process --workers 4 --max-jobs 10
```

### `content-ai queue retry`

Reset all failed jobs to pending status.

```bash
content-ai queue retry [--db queue.db]
```

**Example:**
```bash
# Retry all failed jobs
content-ai queue retry

# Then process them
content-ai queue process
```

### `content-ai queue clear`

Clear all jobs from queue.

```bash
content-ai queue clear [--db queue.db] [--manifest]
```

**Options:**
- `--manifest`: Also clear state transition logs (full reset)

**Example:**
```bash
# Clear queue (keep manifest cache)
content-ai queue clear

# Full reset (clear everything)
content-ai queue clear --manifest
```

---

## Resume & Dirty Detection

### How Resume Works

When you run `content-ai process --input ./videos`:

1. **Scan Directory**: Find all video files matching extensions
2. **For Each Video**:
   - Compute input hash (two-tier: quick + full)
   - Compute config hash (SHA-256 of resolved config)
   - Check if item exists in manifest

3. **Decision Logic**:
   ```
   IF item NOT in manifest:
       ➜ Enqueue as NEW job

   ELSE IF item status is SUCCEEDED:
       Compare hashes (config + input):

       IF hashes match:
           ➜ Skip (cache hit)

       ELSE:
           ➜ Mark DIRTY + re-enqueue

   ELSE IF item status is FAILED:
       IF retry allowed:
           ➜ Re-enqueue
       ELSE:
           ➜ Skip (max attempts reached)

   ELSE IF item status is PENDING/RUNNING:
       ➜ Re-enqueue (idempotent)
   ```

### Two-Tier Hashing Strategy

**Why Two Tiers?**

- **Quick Hash**: Fast check using file size + 5 sample positions (SHA-256)
  - Detects most changes instantly (size change, content edits)
  - Takes <1 second even for 200MB files

- **Full Hash**: BLAKE2b of entire file content
  - Accurate detection of subtle changes
  - Takes ~4 seconds for 200MB files
  - Only computed if quick hash differs

**Algorithm:**

```python
def compute_input_hash(video_path):
    stat = os.stat(video_path)

    # Tier 1: Quick hash (size + 5 samples)
    quick_hasher = hashlib.sha256()
    quick_hasher.update(str(stat.st_size).encode())

    sample_positions = [0, 0.25, 0.5, 0.75, 1.0]
    for pos in sample_positions:
        offset = int(stat.st_size * pos)
        f.seek(offset)
        quick_hasher.update(f.read(1MB))

    # Tier 2: Full content hash (BLAKE2b)
    full_hasher = hashlib.blake2b()
    for chunk in iter(lambda: f.read(64KB), b''):
        full_hasher.update(chunk)

    return {
        'quick_hash': quick_hasher.hexdigest(),
        'full_hash': full_hasher.hexdigest(),
        'size': stat.st_size
    }
```

**Comparison Logic:**

```python
def verify_hashes(stored, current):
    # Fast rejection: size changed
    if stored['size'] != current['size']:
        return False, "File size changed"

    # Quick hash match = probably unchanged
    if stored['quick_hash'] == current['quick_hash']:
        return True, "Content unchanged (quick hash match)"

    # Full hash comparison (slow but accurate)
    if stored['full_hash'] != current['full_hash']:
        return False, "File content changed"

    # Quick hash changed but full hash same = metadata-only change
    return True, "Metadata changed, content unchanged"
```

### Config Change Detection

**Config Hash:**

```python
def compute_config_hash(config):
    """SHA-256 of sorted, serialized config JSON."""
    config_dict = config.model_dump()  # Pydantic model → dict
    config_json = json.dumps(config_dict, sort_keys=True, indent=None)
    return hashlib.sha256(config_json.encode()).hexdigest()
```

**Example Scenario:**

```bash
# Initial run with default config
$ content-ai process --input ./videos
# All videos processed, marked SUCCEEDED

# User changes config
$ content-ai process --input ./videos --rms-threshold 0.15

# Output:
# Enqueueing 50 videos...
#   ⚠ Dirty: video_001.mp4 (Config changed)
#   ⚠ Dirty: video_002.mp4 (Config changed)
#   ...
```

---

## Performance & Concurrency

### Worker Pool Architecture

**ProcessPoolExecutor** is used instead of threading because:
- Video processing is CPU-bound (HPSS, RMS computation)
- ProcessPoolExecutor bypasses Python's GIL for true parallelism
- Each worker gets pre-loaded libraries (librosa, moviepy) for efficiency

**Worker Initialization:**

```python
def _worker_init():
    """Runs once per worker process."""
    import librosa  # Pre-load heavy libraries
    import moviepy

    # Set worker-specific temp directory
    worker_tmp = f'/tmp/content_ai_worker_{os.getpid()}'
    os.makedirs(worker_tmp, exist_ok=True)
    os.environ['TMPDIR'] = worker_tmp
```

**Benefits:**
- Libraries loaded once per worker (not per video)
- Isolated temp directories prevent file conflicts
- Clean shutdown on SIGTERM/SIGINT

### Heartbeat System

**Problem:** Long-running video processing (5-10 minutes for large files) can appear "stale" in crash recovery.

**Solution:** Worker processes update heartbeat timestamp every 60 seconds.

**Implementation:**

```python
def _start_heartbeat(db_path, job_id):
    """Background thread updates heartbeat every 60s."""
    stop_event = threading.Event()

    def heartbeat_loop():
        # Create thread-local SQLite connection
        manifest = SQLiteManifest(db_path)
        queue = SQLiteQueue(manifest)

        while not stop_event.is_set():
            queue.update_heartbeat(job_id)
            time.sleep(60)

    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.start()
    return (thread, stop_event)
```

**Stale Job Detection:**

```python
def reset_stale_running(timeout_s=7200):
    """Reset jobs stuck in RUNNING state."""
    cutoff = datetime.now() - timedelta(seconds=600)

    # Mark as stale if:
    # - No heartbeat in 10 minutes
    # - OR started > 2 hours ago with no heartbeat
    UPDATE job_items
    SET status = 'pending', worker_id = NULL
    WHERE status = 'running'
      AND (last_heartbeat < ? OR started_at < ?)
```

### Performance Metrics

**Test Results** (207MB gameplay video):

| Metric | Value |
|--------|-------|
| Hash Computation (Quick) | <1 second |
| Hash Computation (Full) | ~4 seconds |
| Detection + Processing | ~20 seconds |
| Rendering (6 clips) | ~5 seconds |
| **Total Processing Time** | **~26 seconds** |
| **Throughput** | ~8.3 MB/s |

**Scaling:**

| Videos | Workers | Time (Sequential) | Time (Parallel) | Speedup |
|--------|---------|-------------------|-----------------|---------|
| 10 | 1 | ~4.3 minutes | ~4.3 minutes | 1x |
| 10 | 4 | ~4.3 minutes | ~1.2 minutes | 3.6x |
| 100 | 1 | ~43 minutes | ~43 minutes | 1x |
| 100 | 8 | ~43 minutes | ~6 minutes | 7.2x |

*Note: Speedup depends on CPU cores and video complexity.*

---

## Error Handling & Recovery

### Error Classification

Errors are classified into **permanent** vs **transient** to determine retry behavior:

**Permanent Errors (No Retry):**
- `FileNotFoundError` - Video file deleted/moved
- `PermissionError` - Insufficient file permissions
- `ValueError` - Invalid input (empty file, corrupt video)
- `OSError` (disk full) - Critical, stops worker

**Transient Errors (Retry):**
- Network errors (if reading from network drive)
- Temporary file lock conflicts
- FFmpeg subprocess crashes
- Memory pressure (occasional OOM)

**Implementation:**

```python
def process_video_job(job, config, db_path, run_dir):
    try:
        # ... process video ...
        queue.ack_success(job_id, result)

    except (FileNotFoundError, PermissionError, ValueError) as e:
        # Permanent error - don't retry
        queue.ack_fail(job_id, error=str(e), retry=False)

    except OSError as e:
        if "No space left" in str(e):
            # Critical - re-raise to stop worker
            raise
        # Other OS errors - retry
        queue.ack_fail(job_id, error=str(e), retry=True)

    except Exception as e:
        # Transient error - retry
        queue.ack_fail(job_id, error=str(e), retry=True)
```

### Retry Logic

**Max Attempts:**

Default: 3 attempts per job (configurable in job metadata)

**Retry Flow:**

```
Attempt 1: PENDING → RUNNING → FAILED (retry=True)
           ↓
Attempt 2: PENDING → RUNNING → FAILED (retry=True)
           ↓
Attempt 3: PENDING → RUNNING → FAILED (retry=False)
           ↓
         Terminal FAILED state
```

**Manual Retry:**

```bash
# Reset all failed jobs to pending
content-ai queue retry

# Process again
content-ai queue process
```

### Crash Recovery

**Scenario:** Worker crashes mid-processing (SIGKILL, OOM, power loss).

**Recovery:**

1. **On Next Run**:
   - Manifest loaded from SQLite (persistent)
   - Jobs in `RUNNING` state detected as "stale"

2. **Stale Job Reset**:
   ```python
   reset_count = queue.reset_stale_running(timeout_s=3600)
   # Marks stale jobs as PENDING
   ```

3. **Re-processing**:
   - Stale jobs re-queued
   - Processed normally with attempt count preserved

**Atomicity Guarantee:**

Jobs are **ONLY** marked as `SUCCEEDED` if:
1. All output files exist
2. Output file hashes computed successfully
3. SQLite transaction commits

**No partial success:** State transitions are atomic (all-or-nothing).

---

## Manifest Schema

### SQLite Tables

#### `job_items`

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | TEXT PRIMARY KEY | UUID |
| `video_path` | TEXT UNIQUE | Absolute path to video |
| `input_hash_quick` | TEXT | Quick hash (size + 5 samples) |
| `input_hash_full` | TEXT | Full content hash (BLAKE2b) |
| `input_size` | INTEGER | File size in bytes |
| `config_hash` | TEXT | SHA-256 of resolved config |
| `status` | TEXT | pending, running, succeeded, failed, dirty |
| `priority` | INTEGER | Higher = processed first |
| `attempt_count` | INTEGER | Retry counter |
| `max_attempts` | INTEGER | Max retry limit |
| `created_at` | TEXT | ISO-8601 timestamp |
| `started_at` | TEXT | When processing began |
| `completed_at` | TEXT | When processing finished |
| `last_heartbeat` | TEXT | Last worker heartbeat |
| `worker_id` | TEXT | Worker that claimed job |
| `last_error` | TEXT | Last error message (truncated) |
| `output_files` | TEXT | JSON array of output paths |
| `output_hashes` | TEXT | JSON map {file: sha256} |
| `metadata` | TEXT | JSON user metadata |

**Indexes:**
- `idx_status` on `status`
- `idx_priority_created` on `(priority DESC, created_at ASC)`

#### `state_transitions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Auto-increment |
| `job_id` | TEXT | Job identifier |
| `from_state` | TEXT | Previous state |
| `to_state` | TEXT | New state |
| `timestamp` | TEXT | ISO-8601 timestamp |
| `worker_id` | TEXT | Worker that caused transition |
| `error_snippet` | TEXT | First 200 chars of error |

**Purpose:** Audit trail for debugging and compliance.

---

## Developer Guide

### Adding Queue Support to New Modules

**1. Create Job Specification:**

```python
from content_ai.queue import JobItem, JobStatus

job = JobItem(
    job_id=str(uuid.uuid4()),
    video_path="/path/to/video.mp4",
    input_hash_quick="...",
    input_hash_full="...",
    input_size=123456,
    config_hash="...",
    status=JobStatus.PENDING,
    metadata={"custom": "data"}
)
```

**2. Enqueue Job:**

```python
from content_ai.queue import SQLiteQueue, SQLiteManifest

manifest = SQLiteManifest("queue.db")
queue = SQLiteQueue(manifest)
queue.enqueue(job)
```

**3. Process Job in Worker:**

```python
from content_ai.queue import process_video_job

result = process_video_job(
    job=job,
    config=config_dict,
    db_path="queue.db",
    run_dir=Path("output/run_001")
)
```

### Testing Queue Logic

**Unit Tests:**

See [tests/test_queue.py](tests/test_queue.py) for examples:

```python
def test_enqueue_dequeue(queue, temp_video):
    job = JobItem(job_id=str(uuid.uuid4()), video_path=temp_video, ...)
    queue.enqueue(job)

    dequeued = queue.dequeue(worker_id='test-worker')
    assert dequeued.job_id == job.job_id
    assert dequeued.status == JobStatus.RUNNING
```

**Integration Tests:**

```bash
# Test with real video
content-ai process --input test_video.mp4 --db test.db

# Check status
content-ai queue status --db test.db

# Verify outputs
ls output/batch_*/
```

### Debugging Queue Issues

**Inspect SQLite Database:**

```bash
sqlite3 queue.db

# List all jobs
SELECT job_id, video_path, status, attempt_count FROM job_items;

# Show failed jobs
SELECT job_id, last_error FROM job_items WHERE status = 'failed';

# View state transitions
SELECT job_id, from_state, to_state, timestamp
FROM state_transitions
ORDER BY timestamp DESC
LIMIT 10;
```

**Enable Debug Logging:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Future Enhancements

### Planned Features

1. **Distributed Execution**
   - Swap SQLite → Redis backend
   - Use Taskiq for distributed task queue
   - Central coordinator for multi-machine processing

2. **Advanced Retry Strategies**
   - Exponential backoff between retries
   - Per-error-type retry policies
   - Circuit breaker for cascading failures

3. **Progress Streaming**
   - WebSocket server for real-time progress
   - Web UI for queue visualization
   - Prometheus metrics export

4. **Cost Tracking**
   - Track compute time per job
   - Estimate batch completion time
   - Resource usage statistics

5. **TTS Integration**
   - Cost-idempotent TTS cache (see ARCHITECTURE.md)
   - Narration overlay support
   - Voice profile management

---

## Troubleshooting

### "Database is locked" Error

**Cause:** Multiple processes accessing same SQLite database without WAL mode.

**Fix:** Ensure WAL mode enabled (automatic in SQLiteManifest):

```python
# Already handled in sqlite_backend.py
self.db.conn.execute("PRAGMA journal_mode=WAL")
```

### Jobs Stuck in RUNNING State

**Cause:** Worker crashed without cleanup.

**Fix:** Reset stale jobs:

```bash
content-ai queue status  # Check if jobs are stale
content-ai queue process  # Automatically resets stale jobs
```

### Config Changes Not Triggering Re-processing

**Cause:** `--force` flag not used, or manifest not detecting config change.

**Fix:**

```bash
# Force re-process all
content-ai process --input ./videos --force

# Or manually clear manifest
content-ai queue clear --manifest
```

### Disk Space Exhaustion

**Cause:** Large batch processing fills disk.

**Prevention:** Worker checks available disk space before processing:

```python
disk_usage = shutil.disk_usage(run_dir)
estimated_size = video_size * 1.5

if disk_usage.free < estimated_size:
    raise OSError("Insufficient disk space")
```

---

## Performance Tuning

### Optimal Worker Count

**Recommendation:**

```bash
# CPU-bound workload (HPSS + RMS)
--workers $(nproc)  # Number of CPU cores

# I/O-bound workload (network drives)
--workers $(($(nproc) * 2))  # 2x CPU cores
```

**Benchmarking:**

```bash
# Test different worker counts
for w in 1 2 4 8; do
    echo "Testing $w workers..."
    time content-ai process --input ./videos --workers $w
done
```

### Database Optimization

**SQLite Performance:**

- ✅ WAL mode enabled (automatic)
- ✅ Indexed queries (priority + created_at)
- ✅ BEGIN IMMEDIATE for atomic dequeue
- ✅ Connection pooling (one per worker)

**Vacuum Database (Reclaim Space):**

```bash
sqlite3 queue.db "VACUUM;"
```

---

## Summary

The queue system provides **production-ready** batch processing with:

- ✅ Crash recovery and resumability
- ✅ Dirty detection (config + input changes)
- ✅ Parallel processing with worker pool
- ✅ Atomic state transitions (ACID guarantees)
- ✅ Retry logic with configurable limits
- ✅ Comprehensive error handling
- ✅ Performance: ~8.3 MB/s throughput

**Tested with 207MB real gameplay footage** - all 8 test categories passing, 79 unit tests, 46% code coverage.

For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).
For test results, see [TEST_RESULTS.md](TEST_RESULTS.md).
