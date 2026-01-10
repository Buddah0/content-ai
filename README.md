# Content AI

**Content AI** is an intelligent pipeline that automatically detects high-energy moments in gameplay footage and generates rhythmic highlight montages. Using audio-first signal processing (HPSS + RMS thresholding), it identifies percussive events like gunshots, explosions, and critical hits, then stitches them into a polished video reel.

## Features

- **Audio-First Detection**: Uses librosa's HPSS (Harmonic-Percussive Source Separation) to isolate combat sounds from background music and voice
- **Smart Merging**: Intelligently merges close-together clips with max duration enforcement and deterministic tie-breaking
- **Batch Processing**: Recursively scans folders to process multiple videos in a single run
- **Robust Rendering**: FFmpeg-based segment extraction and concatenation with process isolation
- **Fully Configurable**: YAML-based configuration with CLI flag overrides and Pydantic validation
- **Demo Mode**: Zero-friction one-command validation with bundled synthetic test video
- **Deterministic Output**: Reproducible results with consistent naming, thresholds, and segment ordering

## Installation

### Requirements

- **Python**: 3.11 or higher
- **FFmpeg**: Must be available on your system (or `imageio-ffmpeg` will be used as fallback on Windows/WSL)

### Method 1: Poetry (Recommended)

Poetry is the source of truth for dependencies. `requirements.txt` is auto-generated for pip compatibility.

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Verify installation
poetry run content-ai check
```

### Method 2: pip (Alternative)

```bash
# Create virtual environment
python -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m content_ai check
```

## Quick Start

### One-Command Demo

Zero-friction validation that the entire pipeline works end-to-end:

```bash
# With Poetry
poetry run content-ai scan --demo

# With pip
python -m content_ai scan --demo
```

This command:
- Auto-generates a synthetic demo video with percussive audio spikes (on first run)
- Detects events using HPSS + RMS analysis
- Applies Smart Merging with configurable parameters
- Outputs `demo_output.mp4` in the repo root
- Prints a detailed run summary
- Exits with code 0 on success

**Expected output:**

```
--- 🎬 DEMO MODE ---
Using demo asset: /path/to/assets/demo/sample.mp4
...
============================================================
RUN SUMMARY
============================================================
Files scanned:        1
Events detected:      X
Segments selected:    Y
Total duration:       Z.XXs
Output path:          /path/to/demo_output.mp4
============================================================

✅ Demo complete! Check demo_output.mp4
```

## Usage

### Basic Commands

**Check dependencies:**

```bash
# Poetry
poetry run content-ai check

# pip
python -m content_ai check
```

**Scan a single file:**

```bash
# Poetry
poetry run content-ai scan --input gameplay.mp4

# pip
python -m content_ai scan --input gameplay.mp4
```

**Batch scan (recursive):**

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
│       ├── renderer.py      # FFmpeg/MoviePy video operations
│       ├── scanner.py       # File discovery
│       ├── segments.py      # Pure segment logic (merge/pad/clamp)
│       ├── demo.py          # Synthetic demo video generation
│       ├── __init__.py
│       └── __main__.py
├── tests/                   # Test suite (60 tests, 45% coverage)
│   ├── test_cli.py          # CLI smoke tests
│   ├── test_config.py       # Config loading + Pydantic validation
│   ├── test_models.py       # Pydantic model validation
│   ├── test_scanner.py      # File scanning + batch processing
│   └── test_segments.py     # Segment merging logic
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

- **Process isolation**: FFmpeg spawned in subprocess to prevent file descriptor leaks
- **Codec**: Uses `libx264` video codec and `aac` audio codec (standard H.264/AAC MP4)
- **Preset**: `ultrafast` preset for speed optimization
- **Concatenation**: FFmpeg concat demuxer (`-f concat -c copy`) for safe assembly without re-encoding
- **Safe file handling**: Original inputs never overwritten; outputs written to new run folders

### Performance Characteristics

- **Bottleneck**: CPU-bound audio analysis (HPSS + RMS)
- **Scaling**: Processing time scales with audio length and sample rate
- **Memory**: Audio processed in-memory for accurate HPSS; consider downsampling very long files
- **Parallel processing**: Not currently implemented; runs process files sequentially

## Roadmap / Next Up

### In Progress: Job Queue + Resumable Runs

Add a manifest-backed run state so batch runs can be queued, resumed, and skip already-processed inputs safely.

**Success criteria:**

- [ ] A persistent run manifest (e.g., JSON) records per-input status, outputs, and config fingerprint
- [ ] Re-running the same command resumes incomplete items and skips completed ones deterministically
- [ ] Planned CLI surface to inspect queue/run status (e.g., `status` or `--resume`/`--force` flags)
- [ ] Clear failure modes and recovery documented (corrupt manifest, changed config, missing files)

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
