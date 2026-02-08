# Content AI

**Content AI** is an intelligent pipeline that automatically detects high-energy moments in gameplay footage and generates rhythmic highlight montages. Using audio-first signal processing (HPSS + RMS thresholding), it identifies percussive events like gunshots, explosions, and critical hits, then stitches them into a polished video reel.

## Features

- **Audio-First Detection**: Uses librosa's HPSS (Harmonic-Percussive Source Separation) to isolate combat sounds from background music and voice
- **Smart Merging**: Intelligently merges close-together clips with max duration enforcement and deterministic tie-breaking
- **Batch Processing**: Recursively scans folders to process multiple videos in a single run
- **Job Queue System**: Resumable batch processing with crash recovery, dirty detection, and parallel execution
- **Robust Rendering**: Production-grade FFmpeg orchestration with process isolation, timeout enforcement, VFR safety, and error classification
- **Mission Control Web UI**: Full-stack dashboard for uploading videos, monitoring real-time progress, and reviewing highlights with deep-linked job history
- **Fully Configurable**: YAML-based configuration, CLI flag overrides, Pydantic validation, and a full Preset UX (quick switch, save/update, import/export, manage drawer)
- **Demo Mode**: Zero-friction one-command validation with bundled synthetic test video
- **Zero-Friction CLI**: Auto-discover videos and process with `content-ai` — no subcommand or flags required
- **Deterministic Output**: Reproducible results with consistent naming, thresholds, and segment ordering

## Installation

### Requirements

- **Python**: 3.11 or higher
- **Node.js**: 18+ (for Web UI)
- **FFmpeg**: Must be available on your system

### 1. Backend Setup

```bash
# Create and activate venv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Web UI Setup

```bash
cd web
yarn install
# Initialize Database
npx prisma generate
```

## Running Mission Control

> [!IMPORTANT]
> You need **two separate terminal windows** running simultaneously for the full experience.

### Terminal 1: Start Backend (FastAPI)
Run this command from the root `content-ai` directory:
```bash
# Start from the root folder
./venv/bin/python -m uvicorn content_ai.api.main:app --app-dir src --reload --port 8000
```

### Terminal 2: Start Frontend (Next.js)
Open a new terminal window and move into the `web` folder:
```bash
# Navigate to web/ and start the UI
cd web
npm run dev
```
Once both are running, open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Roadmap

### 1. Robust Rendering ✨ **DONE**
- FFmpeg process isolation
- Timeout enforcement
- VFR to CFR normalization
- Fallback logic for empty detection

### 2. Mission Control Web UI ✨ **DONE**
- Modern Next.js Dashboard
- Real-time SSE Progress
- Job History & Persistence
- Deep-linking to results

### 3. Fully Configurable ✨ **DONE**

- YAML-based configuration
- CLI flag overrides
- Pydantic validation
- Dynamic config injection into Web UI
- Preset UX: quick switch, dirty tracking, save/update, import/export, manage drawer

### 4. Demo Mode ✨ **DONE**

- Synthetic test video with known percussive spikes
- Zero-friction pipeline validation via `content-ai scan --demo`

### 5. Zero-Friction CLI ✨ **DONE**

- `content-ai` with no args auto-discovers videos in CWD
- Positional path: `content-ai ./videos` or `content-ai clip.mp4`
- Always recursive, always queue pipeline
- All existing subcommands unchanged (backward compatible)

### 6. Output Format Support (WebM/VP9)

### 6. TTS Narration Overlay

## Repo Tour (Folder Structure + Golden Path)

### What This Repo Does

Content AI detects high-energy moments in gameplay footage using audio-first signal processing (HPSS + RMS) and generates rhythmic highlight montages automatically.

### Where to Start Reading

Start with [src/content_ai/cli.py](src/content_ai/cli.py) — the CLI entry point that dispatches to either the sequential pipeline (`scan` command) or the queue-based pipeline (`process` command). This module defines all user-facing commands and argument parsing.

### Directory Structure

```
content-ai/
├── src/
│   └── content_ai/           # Core package (src layout)
│       ├── cli.py            # CLI entry point (commands: scan, process, queue, check)
│       ├── pipeline.py       # Sequential pipeline: scan → detect → select → render
│       ├── queued_pipeline.py # Queue-based batch processing wrapper
│       ├── detector.py       # Audio-first detection (HPSS + RMS thresholding)
│       ├── segments.py       # Segment logic (merge, pad, clamp, filter)
│       ├── renderer.py       # Robust rendering with VFR safety
│       ├── ffmpeg_runner.py  # FFmpeg orchestration (timeout, progress)
│       ├── scanner.py        # File discovery (recursive, extension filtering)
│       ├── config.py         # YAML config loader + CLI override merging
│       ├── models.py         # Pydantic data models (validation)
│       ├── demo.py           # Synthetic demo video generation
│       ├── queue/            # Job queue system (resumable runs)
│       │   ├── models.py     # Queue data models (JobItem, JobStatus)
│       │   ├── backends.py   # Abstract interfaces (QueueBackend, ManifestStore)
│       │   ├── sqlite_backend.py # SQLite implementation (ACID guarantees)
│       │   ├── worker.py     # Worker pool + job processing
│       │   └── hashing.py    # Two-tier input/config fingerprinting
│       ├── __init__.py
│       └── __main__.py       # Package entry point
├── tests/                    # Test suite (123 tests, 55% coverage)
│   ├── test_cli.py           # CLI smoke tests
│   ├── test_config.py        # Config loading + Pydantic validation
│   ├── test_models.py        # Pydantic model validation
│   ├── test_scanner.py       # File scanning + batch processing
│   ├── test_segments.py      # Segment merging logic
│   ├── test_queue.py         # Queue system tests
│   ├── test_ffmpeg_runner.py # FFmpeg runner tests
│   └── test_renderer.py      # Renderer + VFR detection tests
├── config/
│   └── default.yaml          # Authoritative defaults (detection, processing, output, rendering)
├── docs/
│   └── RENDERING.md          # Robust rendering system documentation
├── output/                   # Generated runs (run_001/, run_002/, ...)
├── pyproject.toml            # Poetry configuration (source of truth)
├── poetry.lock               # Locked dependencies
├── requirements.txt          # Auto-generated from Poetry (pip fallback)
├── make_reel.py              # Legacy wrapper (backward compatibility)
├── ARCHITECTURE.md           # Architecture decision record
├── copilot.md                # Design principles + pipeline philosophy
└── README.md                 # This file
```

### Walkthrough (Professional)

**Top-Level Directories:**

- **`src/content_ai/`** — Core package. All pipeline logic, CLI commands, queue system, and rendering code live here. Changes to detection algorithms, segmentation rules, or rendering strategy go here.

- **`tests/`** — Test suite. Unit tests for all modules. Add new test files here when introducing new modules. Coverage target: 80%+.

- **`config/`** — Configuration defaults. `default.yaml` is the source of truth for all pipeline parameters. User overrides go in `config/local.yaml` (git-ignored). CLI flags take precedence over YAML.

- **`output/`** — Run artifacts. Each execution creates a timestamped directory (`run_001/`, `run_002/`, ...) containing montage video, metadata JSON, and resolved config. Never commit this directory.

**Core Modules (Inside `src/content_ai/`):**

- **`cli.py`** — CLI surface. Defines all commands (`scan`, `process`, `queue`, `check`) using `click`. Maps CLI arguments to pipeline functions. Add new commands here.

- **`pipeline.py`** — Sequential pipeline orchestrator. Entry point: `run_scan()`. Coordinates scanner → detector → segment processor → renderer. Handles demo mode and run metadata. Use this for single-file or simple batch processing.

- **`queued_pipeline.py`** — Queue-based batch processing. Wraps `pipeline.py` with resumable runs, dirty detection, and parallel worker pool. Use this for large batch jobs requiring crash recovery.

- **`detector.py`** — Audio-first detection. Uses librosa HPSS to separate percussive audio, computes RMS energy, applies fixed threshold. Returns raw event timestamps with peak scores. Changes to detection algorithms go here.

- **`segments.py`** — Pure segment logic. Functions: `pad_segments()`, `merge_segments()`, `clamp_segments()`, `filter_min_duration()`. No I/O, no side effects. Changes to merging rules, max duration enforcement, or tie-breaking go here.

- **`renderer.py`** — Robust rendering with VFR safety. `render_segment_with_runner()` extracts clips using FfmpegRunner with timeout enforcement. `probe_video()` detects VFR sources. Legacy `render_segment_to_file()` preserved for backward compatibility.

- **`ffmpeg_runner.py`** — FFmpeg orchestration. Process isolation, dual timeout (global + no-progress), progress monitoring, error classification, artifact preservation. See [docs/RENDERING.md](docs/RENDERING.md).

- **`scanner.py`** — File discovery. Recursively scans directories, filters by extension, applies limit. Returns list of absolute paths. Changes to file filtering logic go here.

- **`config.py`** — Config resolution. Loads `default.yaml`, merges `local.yaml`, applies CLI overrides. Returns Pydantic-validated config dict. Changes to config schema or precedence rules go here.

- **`models.py`** — Pydantic validation. Data models for config (`ContentAIConfig`), segments (`Segment`), and detection events (`DetectionEvent`). Changes to validation rules or data schemas go here.

- **`demo.py`** — Demo mode. Generates synthetic test video with known percussive spikes on first run. Used by `--demo` flag for smoke testing.

**Queue System (Inside `src/content_ai/queue/`):**

- **`models.py`** — Queue data models. `JobItem`, `JobStatus`, `JobResult`. Pydantic validation for queue operations.

- **`backends.py`** — Abstract interfaces. `QueueBackend` and `ManifestStore` define contracts for queue implementations. Future Redis/Cloud backends implement these.

- **`sqlite_backend.py`** — SQLite implementation. ACID-compliant manifest store with atomic enqueue/dequeue. Uses WAL mode for concurrency. Schema: `job_items`, `state_transitions`.

- **`worker.py`** — Worker pool. `ProcessPoolExecutor` for parallel processing. Pre-loads librosa/moviepy per worker. Heartbeat threads for long jobs.

- **`hashing.py`** — Two-tier hashing. Quick hash (size + 5 samples, <1s) for dirty detection. Full hash (BLAKE2b, ~4s) for validation. Config hash (SHA-256) for parameter change detection.

**Golden Path Flow (Sequential Pipeline):**

```
CLI (cli.py)
  ↓
run_scan() in pipeline.py
  ↓
scan_input() in scanner.py → list of video paths
  ↓
detect_hype() in detector.py → raw event timestamps
  ↓
pad_segments() → merge_segments() → clamp_segments() in segments.py
  ↓
Sorting by order (chronological/score/hybrid)
  ↓
render_segment_to_file() in renderer.py → individual clips
  ↓
build_montage_from_list() in renderer.py → final montage MP4
  ↓
Save metadata (segments.json, resolved_config.json, run_meta.json)
```

**Golden Path Flow (Queue-Based Pipeline):**

```
CLI (cli.py: process command)
  ↓
run_queued_pipeline() in queued_pipeline.py
  ↓
scan_input() → compute hashes → dirty detection → enqueue jobs
  ↓
Worker pool (worker.py) dequeues jobs in parallel
  ↓
Each worker runs: detect → process → render (same as sequential)
  ↓
Ack success/failure → update manifest → next job
  ↓
Resume support: skip cached jobs, re-process dirty jobs
```

### AI Orientation (Quick Reference)

1. **Config files:** `config/default.yaml` is authoritative. CLI flags override YAML. Pydantic validates all config at load time.

2. **CLI entry points:** `src/content_ai/cli.py` defines all commands. `poetry run content-ai <command>` dispatches here.

3. **Core pipeline logic:** `src/content_ai/pipeline.py` orchestrates scan → detect → select → render. Start here for understanding end-to-end flow.

4. **Tests:** `tests/` directory. Run `poetry run pytest` to execute. Add tests for new modules. Coverage target: 80%+.

5. **Avoid touching casually:** `queue/sqlite_backend.py` (ACID-critical), `renderer.py` (FFmpeg subprocess handling), `models.py` (Pydantic schemas affect entire codebase).

6. **Safe to modify:** `segments.py` (pure functions), `scanner.py` (file I/O only), `demo.py` (isolated test asset generation).

7. **Where configs live:** `config/default.yaml` (defaults), `config/local.yaml` (user overrides, git-ignored), CLI flags (highest precedence).

8. **Where tests are:** `tests/` directory. 79 tests across 6 files. 46% coverage (target: 80%+).

9. **Where output goes:** `output/run_###/` for sequential runs, `output/batch_###/` for queue-based runs. Never commit output directory.

10. **Determinism guarantee:** Same inputs + same config → same outputs. Only external factors: FFmpeg version, thread scheduling.

### Where to Add New Features (Extension Map)

**Robust Rendering:**
- **Files:** [src/content_ai/renderer.py](src/content_ai/renderer.py), [src/content_ai/pipeline.py](src/content_ai/pipeline.py) (rendering phase)
- **Boundary:** Rendering starts after segment selection. Inputs: segment list with timestamps. Outputs: MP4 clips + final montage.
- **Invariant:** Original inputs never modified. Outputs written to new run directories. FFmpeg errors must fail loudly (no silent failures).
- **Failure modes:** Invalid timestamps (clamped), subprocess crashes (caught and raised), file descriptor leaks (context managers).

**Adding/Changing Detectors:**
- **Files:** [src/content_ai/detector.py](src/content_ai/detector.py), [config/default.yaml](config/default.yaml) (detection section)
- **Boundary:** Detection takes video path + config, returns list of raw event timestamps with scores. No segment merging or rendering here.
- **Invariant:** Detection must be deterministic (same video + config → same events). No side effects (no file writes).

**Changing Segmentation Logic:**
- **Files:** [src/content_ai/segments.py](src/content_ai/segments.py), [config/default.yaml](config/default.yaml) (processing section)
- **Boundary:** Pure functions only. No I/O, no side effects. Input: list of raw events. Output: processed segments (padded, merged, clamped).
- **Invariant:** Max duration enforcement must preserve highest-scoring segment on tie-breaks. Deterministic ordering (no random selection).

**Adding a New Output Format:**
- **Files:** [src/content_ai/renderer.py](src/content_ai/renderer.py) (add new render function), [src/content_ai/models.py](src/content_ai/models.py) (add config field)
- **Boundary:** Rendering layer only. Extend `build_montage_from_list()` or add new function. CLI flag to select format.
- **Invariant:** Must maintain determinism (same inputs → same outputs). No lossy conversions without user consent.

**Adding CLI Flags/Config:**
- **Files:** [src/content_ai/cli.py](src/content_ai/cli.py) (add flag), [src/content_ai/config.py](src/content_ai/config.py) (merge logic), [src/content_ai/models.py](src/content_ai/models.py) (Pydantic schema)
- **Precedence:** CLI flags > `config/local.yaml` > `config/default.yaml`
- **Invariant:** All config must pass Pydantic validation. Breaking changes require version bump.

**Adding Queue Features:**
- **Files:** [src/content_ai/queue/](src/content_ai/queue/) (all modules), [src/content_ai/queued_pipeline.py](src/content_ai/queued_pipeline.py) (orchestration)
- **Boundary:** Queue system wraps pipeline logic. No changes to detection/rendering. Manifest schema changes require migration.
- **Invariant:** ACID guarantees for state transitions. No partial job success. Dirty detection must be deterministic.

---

## Usage

### Quick Start (Zero-Friction Mode)

Just run `content-ai` in a folder with videos — it auto-discovers files, processes them through the queue pipeline with recursive scanning, and generates montages with sensible defaults.

```bash
# Auto-discover videos in current directory
content-ai

# Process a specific folder or file
content-ai ./videos
content-ai clip.mp4

# With options
content-ai ./videos -w 4 -f --rms-threshold 0.15
```

Run `content-ai --help` to see all available options and subcommands.

### Basic Commands

**Check dependencies:**

```bash
# Poetry
poetry run content-ai check

# pip
python -m content_ai check
```

**Scan a single file (sequential pipeline):**

```bash
# Poetry
poetry run content-ai scan --input gameplay.mp4

# pip
python -m content_ai scan --input gameplay.mp4
```

**Batch scan (recursive, sequential):**

```bash
# Poetry
poetry run content-ai scan --input ./raw_videos --recursive

# pip
python -m content_ai scan --input ./raw_videos --recursive
```

### CLI Flags

Override default configuration values:

```bash
content-ai scan --input ./videos \
  --recursive \
  --rms-threshold 0.15 \
  --max-duration 120 \
  --max-segments 15 \
  --order score \
  --keep-temp
```

**Available flags:**

- `--input, -i`: Input file or directory (required unless using `--demo`)
- `--demo`: Run demo mode with synthetic test video
- `--output, -o`: Output directory (default: `output`)
- `--recursive, -r`: Recursively scan subdirectories
- `--ext`: Comma-separated file extensions (default: `mp4,mov,mkv,avi`)
- `--limit`: Maximum number of input files to process
- `--rms-threshold`: Override RMS energy threshold for event detection
- `--max-duration`: Maximum montage duration in seconds
- `--max-segments`: Maximum number of segments in final montage
- `--order`: Segment ordering strategy (`chronological`, `score`, `hybrid`)
- `--keep-temp`: Keep intermediate clip files (default: delete)

### Queue-Based Batch Processing

✨ **NEW** - Resumable batch processing with crash recovery and parallel execution.

**Process videos with queue system:**

```bash
# Basic batch processing (enqueue + process)
content-ai process --input ./raw_videos --output ./processed

# Resume after crash (skips completed videos)
content-ai process --input ./raw_videos

# Parallel processing with 8 workers
content-ai process --input ./raw_videos --workers 8

# Override config (triggers dirty detection & re-processing)
content-ai process --input ./raw_videos --rms-threshold 0.15
```

**Manage queue:**

```bash
# Check status
content-ai queue status

# Retry failed jobs
content-ai queue retry

# Process existing queue
content-ai queue process --workers 4

# Clear queue
content-ai queue clear
```

**Key Features:**

- **Resume Support**: Automatically skips already-processed videos (cache hits)
- **Dirty Detection**: Re-processes videos when config or input changes
- **Crash Recovery**: Resume after interruptions without losing progress
- **Parallel Execution**: Leverage multiple CPU cores for faster processing
- **Retry Logic**: Automatically retry transient failures (configurable limits)

See [QUEUE.md](QUEUE.md) for comprehensive queue system documentation.

### Legacy Mode

The original script wrapper is preserved for backward compatibility:

```bash
python make_reel.py gameplay.mp4
```

## Configuration

### YAML Configuration File

Defaults are defined in `config/default.yaml`. Create `config/local.yaml` for user-specific overrides (ignored by git).

**Precedence rules:**
```
CLI flags > config/local.yaml > config/default.yaml
```

### Configuration Reference

| Key | Type | Default | Description | Used In |
|-----|------|---------|-------------|---------|
| **detection.rms_threshold** | float | `0.10` | Minimum RMS energy to consider an event (range: 0.0–1.0) | detector.py |
| **detection.min_event_duration_s** | float | `0.1` | Minimum event duration in seconds | detector.py |
| **detection.hpss_margin** | tuple | `[1.0, 5.0]` | HPSS margins for harmonic/percussive separation | detector.py |
| **processing.context_padding_s** | float | `1.0` | Pre/post-roll padding around each event in seconds | segments.py |
| **processing.merge_gap_s** | float | `2.0` | Maximum gap to merge adjacent segments in seconds | segments.py |
| **processing.max_segment_duration_s** | float | `10.0` | Maximum duration for any merged segment in seconds | segments.py |
| **output.max_duration_s** | int | `90` | Maximum length of final montage in seconds | pipeline.py |
| **output.max_segments** | int | `12` | Maximum number of segments in montage | pipeline.py |
| **output.order** | string | `"chronological"` | Sorting strategy: `chronological`, `score`, `hybrid` | pipeline.py |
| **output.keep_temp** | bool | `false` | Whether to keep intermediate clip files | pipeline.py |

**Example `config/local.yaml`:**

```yaml
detection:
  rms_threshold: 0.15  # Higher threshold for less noisy sources

processing:
  merge_gap_s: 3.0     # Merge segments closer than 3s

output:
  max_duration_s: 120  # 2-minute montages
  order: "score"       # Sort by energy score
```

## Architecture

### Pipeline Flow

```
Scanner → Detector → Segment Processor → Renderer
   ↓          ↓             ↓                ↓
 Files    Events        Segments         Montage
```

### Module Responsibilities

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| **scanner.py** | File discovery and input sanitization | `scan_input()`: Walks directories, filters by extension |
| **detector.py** | Audio-first analysis using HPSS + RMS | `detect_hype()`: Extracts audio, runs HPSS, detects percussive events |
| **segments.py** | Pure logic for segment operations | `merge_segments()`, `pad_segments()`, `clamp_segments()`, `filter_min_duration()` |
| **renderer.py** | FFmpeg/MoviePy orchestration | `render_segment_to_file()`, `build_montage_from_list()`, `check_ffmpeg()` |
| **pipeline.py** | Orchestrates scan → detect → select → render | `run_scan()`: Main entry point coordinating all modules |
| **cli.py** | Public CLI surface and argument mapping | `main()`: Parses args, invokes pipeline |
| **config.py** | YAML loader with Pydantic validation | `resolve_config()`: Merges defaults, local overrides, CLI flags |
| **models.py** | Pydantic data models for validation | `ContentAIConfig`, `Segment`, `DetectionEvent` |
| **demo.py** | Synthetic demo video generation | `get_demo_asset_path()`, `generate_demo_video()` |

### Output Structure

Each run creates a timestamped directory under `output/`:

```
output/
├── run_001/
│   ├── montage.mp4           # Final output video
│   ├── segments.json         # Selected segments with metadata
│   ├── resolved_config.json  # Exact runtime configuration
│   └── run_meta.json         # Run summary (files, events, duration)
├── run_002/
│   └── ...
```

**Demo mode outputs:**
- `demo_output.mp4` in repo root
- Metadata saved to `output/demo_run/`

## Smart Merging

Smart Merging is the core post-processing logic that transforms raw detected events into intelligent, viewer-friendly segments.

### How It Works

1. **Padding**: Apply pre-roll and post-roll (`context_padding_s`) to each raw event
2. **Clamping**: Constrain padded segments to video duration boundaries
3. **Merging**: If gap between segments < `merge_gap_s`, merge them into one
4. **Max Duration Enforcement**: If merging would exceed `max_segment_duration_s`, keep the segment window with highest peak energy (deterministic tie-breaking)
5. **Filtering**: Remove segments shorter than `min_event_duration_s`

### Guardrails

- **Max duration cap**: Prevents excessively long merged segments that lose viewer attention
- **Deterministic tie-breaking**: When two segments have equal score, keeps the first encountered (chronological priority)
- **Boundary clamping**: Ensures segments never exceed video start/end times
- **Score preservation**: Merged segments retain the highest peak RMS score from constituent events

### Known Limitations

- Audio-driven detection can be noisy depending on music/voice mix in source material
- Results vary based on source loudness and percussive clarity
- Over-merging can occur with very low `merge_gap_s` values
- Under-merging can occur with very high `rms_threshold` values

## Demo Command Philosophy

The demo command embodies the project's commitment to **deterministic, reproducible output**:

- **Synthetic test data**: Auto-generated demo video with known percussive spikes at specific timestamps
- **Predictable thresholds**: Uses default config values (`rms_threshold=0.10`, `merge_gap_s=2.0`, etc.)
- **Deterministic naming**: Output always goes to `demo_output.mp4`
- **Run summary**: Prints files scanned, events detected, segments selected, total duration
- **Exit code contract**: Exits with 0 on success, non-zero on failure

This design ensures the demo serves as both:
1. **Zero-friction onboarding** for new users
2. **Smoke test** validating the entire pipeline in CI/CD

## Project Structure

```
content-ai/
├── src/
│   └── content_ai/          # Core package (src layout)
│       ├── cli.py           # Command-line interface
│       ├── config.py        # YAML loader + Pydantic validation
│       ├── models.py        # Pydantic data models
│       ├── detector.py      # HPSS + RMS audio analysis
│       ├── pipeline.py      # Orchestrates scan → detect → render
│       ├── queued_pipeline.py  # ✨ Queue-based batch processing wrapper
│       ├── renderer.py      # FFmpeg/MoviePy video operations
│       ├── scanner.py       # File discovery
│       ├── segments.py      # Pure segment logic (merge/pad/clamp)
│       ├── demo.py          # Synthetic demo video generation
│       ├── queue/           # ✨ Job queue system (NEW)
│       │   ├── __init__.py
│       │   ├── backends.py  # Abstract interfaces (QueueBackend, ManifestStore)
│       │   ├── models.py    # Queue data models (JobItem, JobResult, JobStatus)
│       │   ├── sqlite_backend.py  # SQLite implementation
│       │   ├── worker.py    # Worker pool + job processing
│       │   └── hashing.py   # Input/config/output fingerprinting
│       ├── __init__.py
│       └── __main__.py
├── tests/                   # Test suite (79 tests, 46% coverage)
│   ├── test_cli.py          # CLI smoke tests
│   ├── test_config.py       # Config loading + Pydantic validation
│   ├── test_models.py       # Pydantic model validation
│   ├── test_scanner.py      # File scanning + batch processing
│   ├── test_segments.py     # Segment merging logic
│   └── test_queue.py        # ✨ Queue system tests (19 tests)
├── config/
│   └── default.yaml         # Authoritative defaults
├── output/                  # Generated runs (run_001, run_002, ...)
├── assets/
│   └── demo/                # Auto-generated on first --demo run
│       └── sample.mp4       # Synthetic test video
├── pyproject.toml           # Poetry configuration (source of truth)
├── poetry.lock              # Locked dependencies
├── requirements.txt         # Auto-generated from Poetry (pip fallback)
├── make_reel.py             # Legacy wrapper (backward compatibility)
├── ARCHITECTURE.md          # Architecture decision record
├── QUEUE.md                 # ✨ Queue system documentation (NEW)
├── TEST_RESULTS.md          # ✨ End-to-end test results (NEW)
├── MIGRATION_SUMMARY.md     # Library migration summary (Poetry, Pydantic, Pytest)
├── copilot.md               # Design principles + pipeline philosophy
└── README.md                # This file
```

## Development

### Setup

```bash
# Install with dev dependencies
poetry install --with dev
```

### Running Tests

```bash
# Run full test suite (60 tests)
poetry run pytest

# Run with coverage
poetry run pytest --cov=content_ai --cov-report=term-missing

# Run specific test file
poetry run pytest tests/test_segments.py -v
```

### Linting

```bash
# Check code with ruff
poetry run ruff check src/ tests/

# Auto-fix issues
poetry run ruff check --fix src/ tests/
```

### Updating Dependencies

```bash
# Add a new dependency
poetry add package-name

# Add a dev dependency
poetry add --group dev package-name

# Update poetry.lock
poetry lock

# Regenerate requirements.txt for pip users
poetry export -f requirements.txt --without-hashes -o requirements.txt
```

## Technical Details

### Audio-First Detection Pipeline

1. **Audio Extraction**: MoviePy extracts audio to temporary WAV file
2. **HPSS Separation**: Librosa splits audio into harmonic and percussive components
3. **RMS Calculation**: Root Mean Square energy computed over hop windows on percussive track
4. **Thresholding**: Fixed threshold (`rms_threshold`) applied to identify high-energy events
5. **Event Collapsing**: Consecutive high-energy frames collapsed into start/end timestamps
6. **Metadata Capture**: Peak RMS score recorded for each event

### Determinism and Reproducibility

- **Processing**: Mostly deterministic given identical inputs and configs
- **External factors**: FFmpeg build version and thread scheduling can introduce minor variation
- **Reproducibility**: Pin dependencies via `poetry.lock` and use identical `config/default.yaml` to reproduce runs
- **Run metadata**: `resolved_config.json` captures exact runtime config for each run

### Rendering Strategy

- **Process isolation**: FFmpeg spawned via `subprocess.Popen` with process tree cleanup
- **Dual timeout**: Global (30 min) + no-progress (2 min) timeout enforcement
- **VFR safety**: Automatic detection and CFR normalization to prevent audio desync
- **Render contract**: H.264 high profile @ 30fps CFR, AAC stereo (configurable)
- **Error classification**: Permanent vs transient for intelligent retry logic
- **Artifact preservation**: Saves logs + reproducible scripts on failure
- **Safe file handling**: Original inputs never overwritten; outputs written to new run folders

See [docs/RENDERING.md](docs/RENDERING.md) for comprehensive rendering documentation.

### Performance Characteristics

- **Bottleneck**: CPU-bound audio analysis (HPSS + RMS)
- **Scaling**: Processing time scales with audio length and sample rate
- **Memory**: Audio processed in-memory for accurate HPSS; consider downsampling very long files
- **Parallel processing**: ✨ **Implemented** - Use `--workers N` for parallel execution (queue-based pipeline)
  - Tested: ~3.6x speedup with 4 workers, ~7.2x speedup with 8 workers
  - Throughput: ~8.3 MB/s per worker (207MB video → 26 seconds)

## Project Status

### Done (Implemented + Working)

**Core Pipeline:**
- ✅ Audio-first detection (HPSS + RMS thresholding) - Evidence: [detector.py](src/content_ai/detector.py)
- ✅ Smart merging with max duration enforcement - Evidence: [segments.py](src/content_ai/segments.py)
- ✅ Robust rendering (FFmpeg concat, process isolation) - Evidence: [renderer.py](src/content_ai/renderer.py)
- ✅ Sequential pipeline (scan → detect → select → render) - Evidence: [pipeline.py](src/content_ai/pipeline.py)
- ✅ Demo mode with synthetic test video - Evidence: [demo.py](src/content_ai/demo.py)

**Configuration & Validation:**
- ✅ YAML config with CLI overrides - Evidence: [config/default.yaml](config/default.yaml), [config.py](src/content_ai/config.py)
- ✅ Pydantic validation for all config and data models - Evidence: [models.py](src/content_ai/models.py)
- ✅ Deterministic output (same inputs → same results) - Evidence: Fixed thresholds, codecs, tie-breaking rules

**Queue System (Resumable Runs):**
- ✅ SQLite-backed manifest with ACID guarantees - Evidence: [queue/sqlite_backend.py](src/content_ai/queue/sqlite_backend.py)
- ✅ Two-tier hashing for dirty detection - Evidence: [queue/hashing.py](src/content_ai/queue/hashing.py)
- ✅ Parallel processing with worker pool (ProcessPoolExecutor) - Evidence: [queue/worker.py](src/content_ai/queue/worker.py)
- ✅ Crash recovery and retry logic - Evidence: Tested with 207MB real gameplay footage
- ✅ CLI commands: `process`, `queue status`, `queue retry`, `queue clear` - Evidence: [cli.py](src/content_ai/cli.py)

**Testing & CI:**

- ✅ 123 unit tests across 8 test files (55% coverage) - Evidence: [tests/](tests/)
- ✅ GitHub Actions CI with Poetry caching - Evidence: [.github/workflows/ci.yml](.github/workflows/ci.yml)

**Robust Rendering:**

- ✅ FfmpegRunner with process isolation - Evidence: [ffmpeg_runner.py](src/content_ai/ffmpeg_runner.py)
- ✅ Dual timeout enforcement (global + no-progress) - Evidence: 30 min global, 2 min stall detection
- ✅ VFR detection and CFR normalization - Evidence: [renderer.py](src/content_ai/renderer.py) `probe_video()`, `should_use_fast_path()`
- ✅ Render contract for consistent output - Evidence: [models.py](src/content_ai/models.py) `RenderContractConfig`
- ✅ Error classification for retry logic - Evidence: [ffmpeg_runner.py](src/content_ai/ffmpeg_runner.py) `FfmpegErrorType`
- ✅ Artifact preservation on failure - Evidence: Saves logs + reproducible scripts

### Next Milestone: Output Format Support 🚧

**Status:** Not Started

**Goal:** Add WebM and other output format support.

**Acceptance Criteria:**

1. Add WebM output format support (VP9 video, Opus audio) with CLI flag `--format webm`
2. Verify output file integrity (checksum validation before marking job succeeded)
3. Add detailed rendering metrics to run_meta.json (render time per clip, total encoding time, codec info)

**Modules to Touch:**

- [renderer.py](src/content_ai/renderer.py) - Add WebM contract support
- [models.py](src/content_ai/models.py) - Add output_format field to OutputConfig
- [cli.py](src/content_ai/cli.py) - Add `--format` flag

**Guardrails:**

- Maintain determinism (same inputs → same outputs for same format)
- Test with diverse videos (high/low motion, different resolutions)
- No silent failures (all FFmpeg errors must be caught and raised)

### Future: TTS Narration

Add text-to-speech narration overlay for automated highlight commentary.

**Features:**
- Generate narration scripts for detected highlights
- Multi-provider support (ElevenLabs, OpenAI TTS, local Piper)
- Cost-idempotent TTS cache (avoid re-billing for same text)
- Audio mixing with ducking (lower game audio during narration)

### Future: Style Replication

Learn editing styles from paired examples (raw footage + final montage) to recreate user preferences automatically.

## Known Issues

- **FFmpeg dependency**: Must be available on PATH or the environment; otherwise rendering will fail or fallback to `imageio-ffmpeg` on Windows/WSL
- **MoviePy version**: Pinned to 1.0.3 due to decorator dependency constraints; API changes in MoviePy 2.x may break rendering integrations in future versions
- **Noisy audio detection**: Results vary significantly based on source material loudness and music/voice mix
- **No visual analysis**: Detection is purely audio-driven; visual cues (kill feed, damage numbers) are not considered

## License

MIT

## Contributing

This project uses Poetry for dependency management and Pydantic for validation. See [Development](#development) for setup instructions.

**Pre-commit checklist:**

```bash
# Lint
poetry run ruff check src/ tests/

# Tests
poetry run pytest

# CLI smoke test
poetry run content-ai check
```

---

**Built with audio-first detection, deterministic output, and zero-friction validation.**
