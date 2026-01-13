# Content AI Architecture

**Project:** content-ai
**Last Updated:** 2026-01-13
**Status:** Production-ready (Queue system implemented + tested)

---

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Data Flow / Pipeline](#data-flow--pipeline)
- [Invariants & Guarantees](#invariants--guarantees)
- [Rendering Terminology (Glossary)](#rendering-terminology-glossary)
- [Extension Points (Detailed)](#extension-points-detailed)
- [Configuration System](#configuration-system)
- [Job Queue System](#job-queue-system)
- [Testing Strategy](#testing-strategy)

---

## Overview

Content AI is a lightweight engine for detecting gameplay highlights (percussive "hype" moments) and creating montages. The project uses **audio-first detection** (HPSS + RMS thresholding) as the core design principle, prioritizing reliability and determinism over adaptive algorithms.

### Design Philosophy

**Audio-First Detection:**
Audio signals (percussive energy) are more reliable for detecting action moments than visual analysis. Visual methods (OCR, object detection) introduce complexity, latency, and fragility. Audio-first keeps the pipeline fast, deterministic, and robust.

**Robust Rendering:**
Rendering prioritizes stability over style. Uses FFmpeg subprocess calls with process isolation, hard cuts only (no transitions), and concat demuxer for safe assembly without re-encoding. If FFmpeg errors, fail loudly and early.

**Deterministic Output:**
Same inputs + same config → same outputs. Codecs, presets, and thresholds are fixed. No randomness in detection, segmentation, or rendering.

---

## Core Components

### 1. Scanner ([scanner.py](src/content_ai/scanner.py))

**Purpose:** File discovery and input sanitization.

**Key Functions:**
- `scan_input(path, recursive, limit, extensions)` — Walks directories, filters by extension, returns list of absolute paths

**Responsibilities:**
- Recursive directory traversal
- Extension filtering (case-insensitive)
- Limit enforcement (max files to process)
- Fail gracefully on permission errors

**Invariants:**
- Must be fast (no video metadata reads during scan)
- Returns absolute paths only
- No side effects (read-only operation)

---

### 2. Detector ([detector.py](src/content_ai/detector.py))

**Purpose:** Audio-first analysis using HPSS + RMS thresholding.

**Key Functions:**
- `detect_hype(video_path, config)` — Extracts audio, runs HPSS, detects percussive events

**Algorithm:**
1. Extract audio to temporary WAV file (MoviePy)
2. Load audio with librosa: `y, sr = librosa.load(temp_audio.wav)`
3. HPSS separation: `y_h, y_p = librosa.effects.hpss(y, margin=config['hpss_margin'])`
4. RMS calculation on percussive track: `rms = librosa.feature.rms(y=y_p)[0]`
5. Fixed threshold: `mask = rms > config['rms_threshold']`
6. Collapse mask to segments: detect start/end of contiguous high-energy frames
7. Filter by `min_event_duration_s`
8. Return list of raw events with timestamps and peak RMS scores

**Invariants:**
- Detection must be deterministic (same video + config → same events)
- No segment merging or rendering here (pure detection)
- No side effects (temp audio cleaned up)

**Failure Modes:**
- Missing audio track → skip video (print warning)
- Corrupt audio → librosa error caught, video skipped
- Very long audio → memory pressure (consider downsampling for >1hr videos)

---

### 3. Segment Processor ([segments.py](src/content_ai/segments.py))

**Purpose:** Pure logic for segment operations (padding, merging, clamping, filtering).

**Key Functions:**
- `pad_segments(segments, pad_s)` — Apply pre-roll and post-roll padding
- `clamp_segments(segments, min_time, max_time)` — Constrain to video boundaries
- `merge_segments(segments, gap_s, max_duration_s)` — Merge close segments with max duration enforcement
- `filter_min_duration(segments, min_dur_s)` — Remove segments shorter than threshold

**Smart Merging Logic:**
1. **Padding:** Apply `context_padding_s` to each raw event
2. **Clamping:** Constrain padded segments to [0, video_duration]
3. **Merging:** If gap between segments < `merge_gap_s`, merge them into one
4. **Max Duration Enforcement:** If merging would exceed `max_segment_duration_s`, keep the segment window with highest peak energy (deterministic tie-breaking)
5. **Filtering:** Remove segments shorter than `min_event_duration_s`

**Invariants:**
- All functions are pure (no I/O, no side effects)
- Deterministic ordering (no random selection)
- Max duration cap prevents excessively long merged segments
- Score preservation: merged segments retain highest peak RMS from constituent events
- Tie-breaking: when two segments have equal score, keep first encountered (chronological priority)

**Edge Cases Handled:**
- Gap exactly at `merge_gap_s` boundary (inclusive merge)
- Overlapping padded events (merged)
- Three or more consecutive events within `merge_gap_s` (iterative merging)
- Segments at video boundaries (clamped to [0, duration])

---

### 4. Renderer ([renderer.py](src/content_ai/renderer.py))

**Purpose:** FFmpeg/MoviePy orchestration for robust rendering.

**Key Functions:**
- `render_segment_to_file(source_path, start, end, output_path)` — Extract single segment to temp file
- `build_montage_from_list(segment_files, output_file)` — Concatenate clips using FFmpeg concat demuxer
- `check_ffmpeg()` — Verify FFmpeg availability

**Rendering Strategy:**

**Segment Extraction:**
- Uses MoviePy `VideoFileClip.subclip(start, end)`
- Timestamps clamped to [0, video.duration] (safety check)
- Codec: `libx264` (H.264 video)
- Audio codec: `aac` (standard MP4 audio)
- Preset: `ultrafast` (optimize for speed)
- Context manager ensures video file closed after use (prevent file descriptor leaks)

**Montage Assembly:**
- FFmpeg concat demuxer: `-f concat -safe 0 -i list.txt -c copy output.mp4`
- Stream copy (`-c copy`) avoids re-encoding (fast, lossless)
- Process isolation: FFmpeg spawned in subprocess
- Stderr captured and printed on error (fail loudly)
- Temp concat list file cleaned up after use

**Invariants:**
- Original inputs never modified (read-only)
- Outputs written to new run directories (timestamped)
- FFmpeg errors must fail loudly (no silent failures)
- Context managers prevent file descriptor leaks
- No audio/video sync tricks (trust FFmpeg defaults)

**Failure Modes Handled:**
- Invalid timestamps → clamped to video bounds
- FFmpeg subprocess crash → caught, stderr printed, exception raised
- File descriptor leaks → prevented by context managers
- Missing FFmpeg → detected at startup via `check_ffmpeg()`

---

### 5. Pipeline Orchestrator ([pipeline.py](src/content_ai/pipeline.py))

**Purpose:** Coordinates scan → detect → select → render flow.

**Key Functions:**
- `run_scan(cli_args)` — Main entry point for sequential pipeline
- `get_run_dir(output_base)` — Create timestamped output directory

**Flow:**
1. Resolve config (merge defaults, local overrides, CLI flags)
2. Handle demo mode (generate synthetic test video if needed)
3. Scan input directory for videos
4. For each video:
   - Detect hype moments
   - Pad, clamp, merge segments
   - Add metadata (source path, unique ID)
5. Global ranking (chronological/score/hybrid)
6. Apply limits (max_segments, max_duration_s)
7. Render clips and montage
8. Save metadata (segments.json, resolved_config.json, run_meta.json)
9. Print run summary

**Invariants:**
- Each run creates new timestamped directory (no overwrites)
- Resolved config saved for reproducibility
- Temp files cleaned unless `keep_temp` flag set
- Demo mode always outputs to `demo_output.mp4` (deterministic path)

---

### 6. CLI Interface ([cli.py](src/content_ai/cli.py))

**Purpose:** Public CLI surface and argument mapping.

**Commands:**
- `scan` — Sequential pipeline (single file or batch)
- `process` — Queue-based batch processing (resumable)
- `queue status` — Show queue statistics
- `queue process` — Process existing queue
- `queue retry` — Retry failed jobs
- `queue clear` — Clear queue
- `check` — Verify FFmpeg availability

**Precedence Rules:**
```
CLI flags > config/local.yaml > config/default.yaml
```

---

### 7. Configuration System ([config.py](src/content_ai/config.py))

**Purpose:** YAML loader with Pydantic validation.

**Key Functions:**
- `resolve_config(cli_args)` — Merges defaults, local overrides, CLI flags
- `get_config_value(config, key, default)` — Helper for both Pydantic/dict access

**Loading Order:**
1. Load `config/default.yaml` (authoritative defaults)
2. Merge `config/local.yaml` if exists (user overrides, git-ignored)
3. Apply CLI flags (highest precedence)
4. Validate with Pydantic models

**Invariants:**
- All config must pass Pydantic validation at load time
- Invalid config raises `ValidationError` with clear messages
- CLI overrides take precedence over YAML
- Resolved config saved to `resolved_config.json` for reproducibility

---

### 8. Data Models ([models.py](src/content_ai/models.py))

**Purpose:** Pydantic data models for validation.

**Models:**
- `ContentAIConfig` — Top-level config (detection, processing, output)
- `DetectionConfig` — RMS threshold, HPSS margins, min duration
- `ProcessingConfig` — Padding, merge gap, max segment duration
- `OutputConfig` — Max duration, max segments, order strategy, keep_temp flag
- `Segment` — Start, end, score (with validation: end > start, score ∈ [0, 1])
- `DetectionEvent` — Timestamp, RMS energy, score

**Validation Examples:**
- `rms_threshold` ∈ [0.0, 1.0]
- `merge_gap_s` ≥ 0.0
- `max_duration_s` > 0
- `order` ∈ {"chronological", "score", "hybrid"}
- Segment `end` > `start` (field validator)

---

## Data Flow / Pipeline

### Sequential Pipeline (scan command)

```
CLI (cli.py)
  ↓
resolve_config() in config.py → Pydantic-validated config
  ↓
scan_input() in scanner.py → list of video paths
  ↓
FOR EACH VIDEO:
  detect_hype() in detector.py → raw event timestamps
  ↓
  pad_segments() → clamp_segments() → merge_segments() in segments.py
  ↓
  Add metadata (source_path, id)
  ↓
Global sorting (chronological/score/hybrid)
  ↓
Apply limits (max_segments, max_duration_s)
  ↓
FOR EACH SEGMENT:
  render_segment_to_file() in renderer.py → clip_###.mp4
  ↓
build_montage_from_list() in renderer.py → montage.mp4
  ↓
Save metadata (segments.json, resolved_config.json, run_meta.json)
  ↓
Print run summary
```

### Queue-Based Pipeline (process command)

```
CLI (cli.py: process command)
  ↓
scan_input() in scanner.py → list of video paths
  ↓
FOR EACH VIDEO:
  Compute input hash (two-tier: quick + full)
  Compute config hash (SHA-256)
  Dirty detection (compare hashes with manifest)
  ↓
  IF new/dirty: enqueue job
  IF succeeded + hashes match: skip (cache hit)
  ↓
Worker pool (ProcessPoolExecutor) spawned
  ↓
EACH WORKER:
  Dequeue job (atomic operation with SQLite BEGIN IMMEDIATE)
  ↓
  Run sequential pipeline (detect → process → render)
  ↓
  Ack success/failure → update manifest → heartbeat thread stops
  ↓
Resume support: skip cached jobs, re-process dirty jobs
```

---

## Invariants & Guarantees

### Determinism

**Goal:** Same inputs + same config → same outputs

**Achieved By:**
- Fixed RMS threshold (no adaptive thresholding)
- Fixed HPSS margins
- Deterministic segment ordering (chronological or score-based)
- Fixed codecs and presets (libx264, aac, ultrafast)
- Tie-breaking rules (first encountered wins on equal scores)

**External Factors (Non-Deterministic):**
- FFmpeg build version (minor encoding differences)
- Thread scheduling (parallel processing order varies)
- File system timestamps (run directory names)

**Reproducibility:**
- Pin dependencies via `poetry.lock`
- Use identical `config/default.yaml`
- Capture resolved config in `resolved_config.json`

### Safety

**Original Inputs Never Modified:**
- All operations are read-only on source videos
- Outputs written to new timestamped directories
- Temp files cleaned up unless `keep_temp` flag set

**Fail Loudly:**
- FFmpeg errors caught and raised with stderr output
- Pydantic validation errors raised with clear messages
- No silent failures (no partial outputs without error)

**Resource Cleanup:**
- Context managers ensure video files closed
- Temp audio files cleaned up after detection
- Concat list files deleted after montage assembly
- Worker processes cleaned up on SIGTERM/SIGINT

### ACID Guarantees (Queue System)

**Atomicity:**
- Job state transitions are atomic (SQLite BEGIN IMMEDIATE)
- No partial job success (all outputs validated before marking succeeded)
- Enqueue/dequeue operations are atomic

**Consistency:**
- Manifest schema enforced by SQLite constraints
- Pydantic validation on all queue operations
- State machine invariants enforced (no invalid transitions)

**Isolation:**
- WAL mode enables concurrent reads while writing
- Single-writer per job (atomic dequeue assigns worker_id)

**Durability:**
- SQLite persists all state to disk
- Crash recovery: stale jobs reset to pending on next run

---

## Rendering Terminology (Glossary)

**Segment:**
A time interval [start, end] representing a single highlight clip. Includes metadata: source video path, peak RMS score, unique ID. After merging, a segment may span multiple original detection events.

**Clip:**
A rendered video file extracted from a segment. One segment → one clip MP4. Stored as `clip_###.mp4` in run directory. Cleaned up unless `keep_temp` flag set.

**Render Plan:**
The final list of segments selected for rendering after sorting and limits applied. Includes source paths, timestamps, and ordering. Saved to `segments.json` for reproducibility.

**Artifact:**
Any output file generated by a run. Includes: montage.mp4, clip_###.mp4, segments.json, resolved_config.json, run_meta.json.

**Template:**
Not used in current architecture. Future feature for style replication (learning editing patterns from paired examples).

**Timeline:**
The original video timeline (0 to duration). All segments are clamped to timeline boundaries to prevent invalid timestamps.

**Overlay:**
Not used in current architecture. Future feature for TTS narration overlay (text-to-speech commentary on highlights).

**Output Directory:**
Timestamped directory (`output/run_###/` or `output/batch_###/`) containing all artifacts for a single run. One directory per run, never overwritten.

**Montage:**
The final concatenated video file assembling all clips in order. Created via FFmpeg concat demuxer with `-c copy` (no re-encoding). Output file: `montage.mp4` or `demo_output.mp4` (demo mode).

**Temp Files:**
Intermediate clip files (`clip_###.mp4`) and concat list files (`concat_list_###.txt`). Cleaned up unless `keep_temp` flag set. Temp audio files (`temp_audio.wav`) always cleaned up.

---

## Extension Points (Detailed)

### ROBUST RENDERING (Priority 1)

**Where Rendering Logic Lives:**
- [src/content_ai/renderer.py](src/content_ai/renderer.py) — Core rendering functions
- [src/content_ai/pipeline.py](src/content_ai/pipeline.py) — Rendering phase (lines 194-226)

**Interfaces:**

**Segment Extraction:**
```python
def render_segment_to_file(source_path: str, start: float, end: float, output_path: str):
    """
    Inputs: source video path, start/end timestamps, output path
    Outputs: clip MP4 file (H.264/AAC, ultrafast preset)
    Failure modes: Invalid timestamps (clamped), MoviePy errors (raised)
    """
```

**Montage Assembly:**
```python
def build_montage_from_list(segment_files: List[str], output_file: str):
    """
    Inputs: list of clip paths, output montage path
    Outputs: final montage MP4 (stream copy, no re-encoding)
    Failure modes: FFmpeg subprocess crash (caught, stderr printed, raised)
    """
```

**Determinism Requirements:**
- Fixed codecs (libx264, aac)
- Fixed preset (ultrafast)
- No random selection in rendering phase
- Same segment list → same montage output

**Failure Handling:**
- Timestamps clamped to [0, video.duration]
- FFmpeg errors caught and raised with stderr
- Context managers prevent file descriptor leaks
- Temp files cleaned up in finally block
- Original inputs never modified

**Conventions:**
- Clip naming: `clip_###.mp4` (zero-padded 3 digits)
- Concat list format: `file '/absolute/path/to/clip.mp4'`
- Temp file naming: `temp_render_audio_{pid}.m4a`, `concat_list_{pid}.txt`
- Config keys: `output.keep_temp` (bool, default False)

**Common Change → Modules/Files → Guardrails:**

1. **Change codec/preset:**
   - Edit: [renderer.py:32-40](src/content_ai/renderer.py#L32-L40)
   - Guardrail: Test with diverse videos (high/low motion, different resolutions)
   - Failure mode: Encoding errors on unsupported codecs

2. **Add transition effects:**
   - Edit: [renderer.py:43-91](src/content_ai/renderer.py#L43-L91) (replace concat with transition rendering)
   - Guardrail: Maintain determinism (no random effects), test memory usage
   - Failure mode: Increased render time, memory pressure

3. **Support new output format (e.g., WebM):**
   - Edit: [renderer.py](src/content_ai/renderer.py) (add new function), [models.py](src/content_ai/models.py) (add config field)
   - Guardrail: Add CLI flag to select format, validate format at config load
   - Failure mode: Unsupported codec/container combinations

4. **Parallel clip rendering:**
   - Edit: [pipeline.py:199-205](src/content_ai/pipeline.py#L199-L205) (replace loop with ProcessPoolExecutor)
   - Guardrail: Ensure temp file naming prevents collisions (use job_id/pid)
   - Failure mode: File descriptor exhaustion, disk I/O contention

---

### Adding/Changing Detectors

**Where Detection Logic Lives:**
- [src/content_ai/detector.py](src/content_ai/detector.py) — HPSS + RMS thresholding
- [config/default.yaml](config/default.yaml) — Detection parameters

**Interfaces:**
```python
def detect_hype(video_path: str, config: dict) -> List[dict]:
    """
    Inputs: video path, config dict (detection section)
    Outputs: list of raw events [{start, end, score, video_duration}]
    Invariant: Deterministic (same video + config → same events)
    Side effects: None (temp audio cleaned up)
    """
```

**Common Change → Modules/Files → Guardrails:**

1. **Change RMS threshold:**
   - Edit: [config/default.yaml](config/default.yaml) (detection.rms_threshold)
   - Guardrail: Valid range [0.0, 1.0], Pydantic validation enforces
   - Failure mode: Threshold too low → too many events, too high → no events

2. **Add visual detection (e.g., kill feed OCR):**
   - Edit: [detector.py](src/content_ai/detector.py) (add new function), [config.py](src/content_ai/config.py) (add config section)
   - Guardrail: Maintain determinism, fallback to audio if visual fails
   - Failure mode: OCR errors on unseen fonts/layouts, increased processing time

3. **Use adaptive threshold:**
   - Edit: [detector.py](src/content_ai/detector.py) (replace fixed threshold with percentile-based)
   - Guardrail: Document determinism loss, add config flag to enable/disable
   - Failure mode: Non-reproducible results, sensitivity to video length

---

### Changing Segmentation Logic

**Where Segmentation Logic Lives:**
- [src/content_ai/segments.py](src/content_ai/segments.py) — Pure functions (merge, pad, clamp, filter)
- [config/default.yaml](config/default.yaml) — Processing parameters

**Interfaces:**
```python
def merge_segments(segments: List[dict], gap_s: float, max_duration_s: float) -> List[dict]:
    """
    Inputs: padded segments, merge gap, max duration
    Outputs: merged segments (with max duration enforcement)
    Invariant: Pure function (no I/O, no side effects)
    Tie-breaking: Highest score wins, chronological on equal scores
    """
```

**Common Change → Modules/Files → Guardrails:**

1. **Change merge gap:**
   - Edit: [config/default.yaml](config/default.yaml) (processing.merge_gap_s)
   - Guardrail: Valid range ≥ 0.0, test edge cases (gap=0, gap=video_duration)
   - Failure mode: Gap too small → over-merging, too large → under-merging

2. **Add cooldown window (prevent back-to-back events):**
   - Edit: [segments.py](src/content_ai/segments.py) (add cooldown filter function)
   - Guardrail: Apply after merging, document interaction with merge_gap
   - Failure mode: Cooldown + merge_gap can over-suppress events

3. **Change tie-breaking rule:**
   - Edit: [segments.py](src/content_ai/segments.py) (modify merge logic)
   - Guardrail: Maintain determinism (no random selection), document new rule
   - Failure mode: Non-deterministic if using timestamps (floating-point precision)

---

### Adding a New Output Format

**Where Rendering Logic Lives:**
- [src/content_ai/renderer.py](src/content_ai/renderer.py) — Rendering functions
- [src/content_ai/models.py](src/content_ai/models.py) — Config schema

**Interfaces:**
```python
def build_montage_webm(segment_files: List[str], output_file: str):
    """
    Inputs: list of clip paths, output path
    Outputs: WebM montage (VP9 video, Opus audio)
    Failure modes: FFmpeg errors (unsupported codec/container)
    """
```

**Common Change → Modules/Files → Guardrails:**

1. **Add WebM output:**
   - Edit: [renderer.py](src/content_ai/renderer.py) (add build_montage_webm), [models.py](src/content_ai/models.py) (add output_format config field)
   - Guardrail: CLI flag `--format webm`, validate codec/container compatibility
   - Failure mode: FFmpeg missing VP9 encoder, slower encoding than H.264

2. **Add JSON-only output (no video):**
   - Edit: [pipeline.py](src/content_ai/pipeline.py) (skip rendering if --json-only flag)
   - Guardrail: Still validate segments, save segments.json
   - Failure mode: None (simplifies output)

---

### Adding CLI Flags/Config

**Where CLI Logic Lives:**
- [src/content_ai/cli.py](src/content_ai/cli.py) — Command definitions and argument parsing
- [src/content_ai/config.py](src/content_ai/config.py) — Config merging logic
- [src/content_ai/models.py](src/content_ai/models.py) — Pydantic schema

**Precedence:**
```
CLI flags > config/local.yaml > config/default.yaml
```

**Common Change → Modules/Files → Guardrails:**

1. **Add new CLI flag:**
   - Edit: [cli.py](src/content_ai/cli.py) (add @click.option), [config.py](src/content_ai/config.py) (map CLI arg to config key), [models.py](src/content_ai/models.py) (add Pydantic field)
   - Guardrail: Pydantic validation enforces type/range, add to help text
   - Failure mode: Typo in config key mapping → override not applied

2. **Add new config section:**
   - Edit: [models.py](src/content_ai/models.py) (add new Pydantic model), [config/default.yaml](config/default.yaml) (add defaults)
   - Guardrail: Add tests for new config section, document in README
   - Failure mode: Breaking change for existing local.yaml files

---

### Adding Queue Features

**Where Queue Logic Lives:**
- [src/content_ai/queue/](src/content_ai/queue/) — All queue modules
- [src/content_ai/queued_pipeline.py](src/content_ai/queued_pipeline.py) — Queue-based pipeline wrapper

**Interfaces:**
```python
def enqueue(self, job: JobItem):
    """
    Inputs: JobItem (video_path, hashes, config_hash, status)
    Side effects: INSERT into job_items table (SQLite)
    Invariant: Atomic operation (BEGIN IMMEDIATE)
    """

def dequeue(self, worker_id: str) -> Optional[JobItem]:
    """
    Outputs: Next pending job (priority-based)
    Side effects: UPDATE status to running, set worker_id
    Invariant: Single-writer (atomic dequeue)
    """
```

**Common Change → Modules/Files → Guardrails:**

1. **Add priority-based processing:**
   - Edit: [sqlite_backend.py](src/content_ai/queue/sqlite_backend.py) (modify dequeue query to ORDER BY priority DESC)
   - Guardrail: Add priority field to JobItem, default=0
   - Failure mode: None (backwards compatible)

2. **Add distributed backend (Redis):**
   - Edit: [backends.py](src/content_ai/queue/backends.py) (implement RedisQueue), [queued_pipeline.py](src/content_ai/queued_pipeline.py) (add --backend flag)
   - Guardrail: Abstract interfaces ensure drop-in replacement
   - Failure mode: Network errors, Redis unavailable (fallback to SQLite)

3. **Add job cancellation:**
   - Edit: [models.py](src/content_ai/queue/models.py) (add CANCELLED status), [sqlite_backend.py](src/content_ai/queue/sqlite_backend.py) (add cancel method)
   - Guardrail: Stop heartbeat thread on cancel, cleanup temp files
   - Failure mode: Race condition if worker already started processing

---

## Configuration System

### YAML Structure

**Source of Truth:** [config/default.yaml](config/default.yaml)

```yaml
detection:
  rms_threshold: 0.10
  min_event_duration_s: 0.1
  hpss_margin: [1.0, 5.0]

processing:
  context_padding_s: 1.0
  merge_gap_s: 2.0
  max_segment_duration_s: 10.0

output:
  max_duration_s: 90
  max_segments: 12
  order: "chronological"  # chronological, score, hybrid
  keep_temp: false
```

### User Overrides

Create `config/local.yaml` (git-ignored):

```yaml
detection:
  rms_threshold: 0.15  # Higher threshold for less noisy sources

output:
  max_duration_s: 120  # 2-minute montages
  order: "score"       # Sort by energy score
```

### CLI Overrides

```bash
content-ai scan --input ./videos --rms-threshold 0.15 --max-duration 120 --order score
```

**Precedence:** CLI flags > local.yaml > default.yaml

---

## Job Queue System

**Status:** ✅ Production-ready (tested with 207MB real gameplay footage)

### Overview

The queue system enables resumable batch processing with crash recovery, dirty detection, and parallel execution. Built on SQLite for zero external dependencies (local-first), with abstract interfaces for future distributed backends.

### Core Components

**1. Manifest Store ([queue/sqlite_backend.py](src/content_ai/queue/sqlite_backend.py))**
- `job_items` table: Stores job state, hashes, outputs, retry counts
- `state_transitions` table: Audit log of all state changes
- Atomic operations using BEGIN IMMEDIATE + WAL mode
- Indexed queries for O(log n) performance

**2. Queue Backend ([queue/sqlite_backend.py](src/content_ai/queue/sqlite_backend.py))**
- Atomic enqueue/dequeue operations
- Priority-based processing (higher priority first)
- Heartbeat tracking for long-running jobs
- Crash recovery (reset stale jobs)

**3. Worker Pool ([queue/worker.py](src/content_ai/queue/worker.py))**
- Parallel processing (bypasses Python GIL)
- Pre-loaded libraries (librosa, moviepy)
- Heartbeat threads for long jobs
- Error classification (permanent vs transient)

**4. Hashing System ([queue/hashing.py](src/content_ai/queue/hashing.py))**
- **Quick hash:** Size + 5 sample positions (SHA-256) — Fast dirty check (<1s)
- **Full hash:** BLAKE2b of entire content — Accurate validation (~4s for 200MB)
- **Config hash:** SHA-256 of sorted config JSON — Detects parameter changes

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

### Resume Logic

On `content-ai process --input ./videos`:

1. Scan directory for videos
2. For each video:
   - Compute input hash (two-tier: quick + full)
   - Compute config hash (SHA-256)
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

### CLI Commands

- `content-ai process --input <path>` — Enqueue + process with queue
- `content-ai queue status` — Show queue statistics
- `content-ai queue process` — Process existing queue
- `content-ai queue retry` — Retry failed jobs
- `content-ai queue clear` — Clear queue

---

## Testing Strategy

### Test Coverage

**Current:** 79 tests, 46% coverage (target: 80%+)

**Breakdown:**
- `test_queue.py`: 19 tests (hash computation, manifest, queue operations)
- `test_segments.py`: 17 tests (segment merging, padding, clamping)
- `test_models.py`: 16 tests (Pydantic validation)
- `test_config.py`: 11 tests (config loading, overrides)
- `test_scanner.py`: 10 tests (file scanning, extension filtering)
- `test_cli.py`: 6 tests (CLI smoke tests)

### Philosophy: Smoke Test Standard

**Do NOT depend on large video files in tests.**

**Preferred Approach:**
- **Synthetic audio:** Generate sine waves, white noise, injected percussive spikes
- **Unit tests:** Test each module independently
- **Integration test:** The `--demo` command itself serves as the integration smoke test

### Required Test Coverage

1. **Scanner:** Empty dirs, invalid paths, permission errors
2. **Detector:** Consistent results on synthetic audio with known peaks
3. **Segments (Smart Merging):**
   - Gap just under/over merge_gap
   - Padding overlap cases
   - Max duration enforcement
   - Deterministic tie-breaking (loudest segment wins)
4. **Renderer:** FFmpeg subprocess handling, concat logic
5. **Queue:** Enqueue/dequeue atomicity, dirty detection, crash recovery

### CI/CD: GitHub Actions

**Minimal, reliable pipeline:**
- Install dependencies via Poetry
- Run pytest (all 79 tests must pass)
- Lightweight check: `content-ai check` (verify FFmpeg availability)
- No heavy assets in CI (tests complete in <2 minutes)

---

## Style Replication Architecture (Planned)

### Overview

Learn editing styles from paired examples (raw footage + final montage) to recreate user preferences automatically.

### Components

**1. Cut Detector (final montage):**
- Detect cuts and segment boundaries in the final montage
- Approaches: Scene detection libraries or audio/visual heuristics

**2. Aligner:**
- Map montage segments to raw timeline
- Approaches:
  - Audio fingerprinting / cross-correlation between montage segments and raw audio
  - Visual matching using quick frames (hashing) if audio alignment is insufficient

**3. Feature Extractor:**
- From aligned pairs compute features:
  - Cut length distributions
  - Padding before/after events
  - Merge thresholds
  - Clip ordering preferences

**4. Style Profile Schema (JSON):**
```json
{
  "version": "1.0",
  "median_padding_s": 0.8,
  "merge_gap_s": 2.5,
  "cut_density": 12.5,  // cuts per minute
  "ranking_weights": {
    "audio_peak": 0.6,
    "visual_salience": 0.3,
    "time_since_last": 0.1
  }
}
```

**5. Style Applier:**
- Takes `style_profile` and modifies detection + post-processing parameters to recreate style

### Inputs & Constraints

- Requires final montage that came from the raw video (same raw source) for direct alignment
- Audio-only alignment works best when montage preserves original audio snippets (no heavy re-mixing)

### Success Criteria

- Recreated montage cut timestamps match expert montage within small tolerance (e.g., ±0.5s) for a majority of cuts
- Quantitative: precision/recall of matched cuts
- Qualitative: human preference tests

### Known Failure Modes & Mitigations

- Misaligned audio (re-mixed or music added): use visual alignment fallback
- Extreme compression in montage: fallback to frame hashing and visual features
- Overcutting from noisy audio: add adaptive median-based thresholding and cooldown/debounce windows

---

**This document is the source of truth for architecture decisions. When in doubt, refer here.**
