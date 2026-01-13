Project Overview
----------------
Content AI: a lightweight engine for detecting gameplay highlights (percussive "hype" moments) and creating a montage. The repository contains a working demo and analysis utilities; the long-term goal is to learn and apply a user's editing style using paired examples of raw gameplay + final montage.

Technical Architecture (pipeline)
--------------------------------
Current (implemented in scripts):
- Audio extraction: `moviepy` extracts audio to a temporary file (e.g., `temp_audio.wav`).
- HPSS separation: `librosa.effects.hpss` to split harmonic vs percussive.
- Detection: RMS on percussive layer; thresholding to create a boolean mask.
- Post-processing: segment duration filter, context padding, small-gap merging.
- Rendering: `moviepy` subclip + concatenate_videoclips -> write video file.

Key Components
- `audio_extractor` (moviepy usage inside scripts)
- `hpss_separation` (librosa)
- `detector` (RMS thresholding + min duration)
- `segment_processor` (padding, merge/bridge)
- `renderer` (moviepy concatenation and write)

Key Logic / Parameters (pseudocode)
----------------------------------
Parameters (as used across current scripts):
- `rms_threshold` (HARD_THRESHOLD / hype_limit)
- `min_event_duration_s` (MIN_DURATION)
- `context_padding_s` (PADDING)
- `merge_gap_s` (MERGE_GAP)

Pseudocode (detection + postprocess):

1. Extract audio -> temp_audio.wav
2. Load audio: y, sr = librosa.load(temp_audio.wav)
3. y_h, y_p = librosa.effects.hpss(y)
4. rms = librosa.feature.rms(y=y_p)[0]
5. times = librosa.times_like(rms, sr=sr)
6. mask = rms > rms_threshold
7. raw_segments = collapse_mask_to_segments(mask, times, min_event_duration_s)
8. padded = [(max(0,s-pad), min(duration, e+pad)) for s,e in raw_segments]
9. final_segments = merge_close_segments(padded, gap=merge_gap_s)

Configuration System
--------------------
- Source of truth: [config/default.yaml](config/default.yaml). This file contains the defaults for input/output paths, detection and edit params, and run params.
- CLI flags (planned) override config keys when provided.
- Per-user overrides: `config/local.yaml` (planned) — ignored by git.

Folder Scanning Architecture
-----------------------------

**Status:** ✅ IMPLEMENTED

Supports both CLI batch mode and config-driven runs with job queue system.

**Implementation:**

- CLI: `content-ai process --input path --output out --recursive [flags]`
- Sequential mode: `content-ai scan --input path --output out --recursive [flags]` (original pipeline)
- Precedence: CLI flags > `config/local.yaml` (user) > `config/default.yaml`
- Output: each run creates `output/batch_###/` with artifacts

**Queue-Based Batch Processing (NEW):**

- Persistent job queue backed by SQLite
- Resumable runs with dirty detection
- Parallel processing with worker pool
- Atomic state transitions (ACID guarantees)
- Crash recovery and retry logic
- See [QUEUE.md](QUEUE.md) for full documentation

batch_meta.json (run metadata)

- Store resolved config (complete, not diff-only)
- Store enqueue stats (enqueued, cached, failed_hash)
- Store process stats (succeeded, failed, skipped)
- Store CLI args and timestamp

Job Queue System Architecture
------------------------------

**Status:** ✅ IMPLEMENTED (Tested with 207MB real gameplay footage)

### Overview

The job queue system enables resumable batch processing with crash recovery, dirty detection, and parallel execution. Built on SQLite for zero external dependencies (local-first), with abstract interfaces for future distributed backends (Redis, Cloud).

### Core Components

**1. Manifest Store (SQLite)**

- **job_items** table: Stores job state, hashes, outputs, retry counts
- **state_transitions** table: Audit log of all state changes
- Atomic operations using BEGIN IMMEDIATE + WAL mode
- Indexed queries for O(log n) performance

**2. Queue Backend (SQLite)**

- Atomic enqueue/dequeue operations
- Priority-based processing (higher priority first)
- Heartbeat tracking for long-running jobs
- Crash recovery (reset stale jobs)

**3. Worker Pool (ProcessPoolExecutor)**

- Parallel processing (bypasses Python GIL)
- Pre-loaded libraries (librosa, moviepy)
- Heartbeat threads for long jobs
- Error classification (permanent vs transient)

**4. Hashing System (Two-Tier)**

- **Quick hash**: Size + 5 sample positions (SHA-256) - Fast dirty check
- **Full hash**: BLAKE2b of entire content - Accurate validation
- **Config hash**: SHA-256 of sorted config JSON - Detects parameter changes

### State Machine

```
pending → running → succeeded
                 ↓
                 → failed → pending (retry)
succeeded → dirty (config/input changed) → running
```

**Invariants:**

- Single-writer per job (atomic dequeue)
- Success implies validation (output files verified)
- Atomic state transitions (SQLite ACID)
- Failed is terminal (requires manual retry)

### Data Flow

```
CLI (process) → Scanner → Hash Computation → Dirty Detection
                                                     ↓
                                        ┌─── Cache Hit? Skip
                                        └─── Dirty/New? Enqueue
                                                     ↓
Worker Pool ← Dequeue ← SQLite Queue ← Enqueue Jobs
    ↓
Process Video (Detection → Processing → Rendering)
    ↓
Ack Success/Failure → Update Manifest → Next Job
```

### Resume Logic

On `content-ai process --input ./videos`:

1. Scan directory for videos
2. For each video:
   - Compute input hash (two-tier)
   - Compute config hash
   - Check manifest:
     - **Not in manifest?** → Enqueue as NEW
     - **Succeeded + hashes match?** → Skip (cache hit)
     - **Succeeded + hash changed?** → Mark DIRTY, re-enqueue
     - **Failed/Pending/Running?** → Re-enqueue

3. Reset stale jobs (stuck in RUNNING > timeout)
4. Process queue with worker pool

### Performance

**Tested with 207MB gameplay video:**

- Hash computation: ~5 seconds (quick + full)
- Detection + Processing: ~20 seconds
- Rendering (6 clips): ~5 seconds
- **Total: ~26 seconds** (~8.3 MB/s throughput)

**Parallel Scaling:**

- 1 worker: baseline
- 4 workers: ~3.6x speedup
- 8 workers: ~7.2x speedup

### Error Handling

**Permanent Errors (No Retry):**

- FileNotFoundError (video deleted)
- PermissionError (insufficient permissions)
- ValueError (corrupt/empty file)

**Transient Errors (Retry):**

- Network errors (network drives)
- FFmpeg subprocess crashes
- Temporary file lock conflicts

**Retry Logic:**

- Max attempts: 3 (configurable)
- Retry flow: PENDING → RUNNING → FAILED → PENDING (retry) → ... → Terminal FAILED
- Manual retry: `content-ai queue retry`

### Crash Recovery

**Scenario:** Worker crashes mid-processing (SIGKILL, OOM, power loss)

**Recovery:**

1. On next run, manifest loaded from SQLite
2. Jobs in RUNNING state detected as "stale"
3. Stale jobs reset to PENDING (with attempt count preserved)
4. Jobs re-processed normally

**Atomicity:** Jobs only marked SUCCEEDED if all output files exist and hashes computed successfully.

### CLI Commands

- `content-ai process --input <path>` - Enqueue + process with queue
- `content-ai queue status` - Show queue statistics
- `content-ai queue process` - Process existing queue
- `content-ai queue retry` - Retry failed jobs
- `content-ai queue clear` - Clear queue

See [QUEUE.md](QUEUE.md) for comprehensive documentation.

---

Style Replication Architecture (Option 1: RAW + FINAL) — Planned
-----------------------------------------------------------------

Overview
- Inputs: raw gameplay video + its final edited montage.
- Output: `style_profile.json` capturing temporal editing preferences (padding, merge decisions, shot ranking, cut density).

Components
- `cut_detector` (final montage): detect cuts and segment boundaries in the final montage (shot boundary detection). Planned approaches: use scene detection libraries or audio/visual heuristics.
- `aligner`: map montage segments to raw timeline. Approaches:
  - Audio fingerprinting / cross-correlation between montage segments and raw audio.
  - Visual matching using quick frames (hashing) if audio alignment is insufficient.
- `feature_extractor`: from aligned pairs compute features such as cut length distributions, padding before/after events, merge thresholds, clip ordering preferences.
- `style_profile` schema (JSON):
  - version
  - median_padding_s
  - merge_gap_s
  - cut_density (cuts per minute)
  - ranking_weights (audio_peak, visual_salience, time_since_last)
- `style_applier`: takes `style_profile` and modifies detection+post-processing parameters to recreate style.

Inputs & Constraints
- Requires final montage that came from the raw video (same raw source) for direct alignment.
- Audio-only alignment works best when the montage preserves original audio snippets (no heavy re-mixing).

Success Criteria & Evaluation
- Recreated montage cut timestamps match expert montage within small tolerance (e.g., ±0.5s) for a majority of cuts.
- Quantitative: precision/recall of matched cuts; qualitative: human preference tests.

Known Failure Modes & Mitigations
- Misaligned audio (re-mixed or music added): use visual alignment fallback.
- Extreme compression in montage: fallback to frame hashing and visual features.
- Overcutting from noisy audio: add adaptive median-based thresholding and cooldown/debounce windows.

Notes
- This document describes current implementation and planned architecture. Items marked "Planned" are not implemented yet and should be scheduled as feature tickets.
