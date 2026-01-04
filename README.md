# Content AI

**Content AI** is an intelligent engine that automatically turns raw gameplay footage into rhythmic "hype montages." It uses audio signal processing to detect percussive events (gunshots, explosions, critical hits) and stitches them together into a high-energy reel.

## 📌 Project Status

### Status Snapshot
- Latest on `main`: `84e2a31` (Jan 2, 2026) — Merge PR for batch processing
- Baseline: `b74547e` (Dec 30, 2025) — initial docs/config + audio scripts
- Current shape: modular pipeline + CLI + batch scanning + config + tests

### ✅ Current Capabilities
- Automated hype detection (audio-first; percussive event detection)
- Batch processing: scan folders recursively
- Robust rendering: ffmpeg-based concatenation / safe video I/O
- Configurable: CLI flags + YAML defaults
- CLI:
  - `python -m content_ai check`
  - `python -m content_ai scan --input ...`
- Tests: starter coverage exists (light unit tests under `tests/`)

### 🚧 In Progress
- Smart Merging (WIP): feature is under active development/tuning; behavior may change

### 🧪 Quick Demo (Golden Path)
1) venv + install deps

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
pip install -r requirements.txt
```

2) Verify environment

```bash
python -m content_ai check
```

3) Batch scan example (recommended)

```bash
python -m content_ai scan --input ./raw_videos --recursive
```

4) Single file example

```bash
python -m content_ai scan --input my_gameplay.mp4
```

5) Legacy mode (wrapper preserved)

```bash
python make_reel.py my_gameplay.mp4
```

### ⚙️ Key Tunables

| Knob | Effect | Typical Default |
| :--- | :--- | :---: |
| `--rms-threshold` | Minimum RMS energy to consider an event | `0.10` |
| `--merge-gap` | Merge segments closer than this (seconds) | `2.0` |
| `--padding` | Padding added before/after each segment (seconds) | `1.0` |
| `--max-duration` | Maximum length of the final montage (seconds) | `90` |
| `--order` | Sorting strategy for output (`chronological`, `score`, `hybrid`) | `chronological` |

### 🧱 Architecture (Reality Check)
- `scanner.py`: file discovery and input sanitization (walks directories, filters extensions)
- `detector.py`: audio-first analysis, HPSS, RMS-based percussive event detection and scoring
- `segments.py`: pure logic for clamping, merging, trimming, and sorting segments
- `renderer.py`: ffmpeg/moviepy orchestration and safe video I/O
- `pipeline.py`: orchestrates scan → detect → select → render
- `cli.py`: public CLI surface and argument mapping
- `config.py`: YAML loader and runtime overrides

### ⚠️ Known Limitations / Gotchas
- Audio-driven detection can be noisy depending on the music/voice mix; results vary by source material
- **FFmpeg**: must be available on PATH or the environment; otherwise rendering will fail or fallback to `imageio-ffmpeg` on Windows/WSL
- MoviePy 2.x is expected; API changes between major MoviePy versions may break rendering integrations

### 🔜 Next Up (Priority Order)
- Finish Smart Merging (WIP) + make it reliable
- "One-command demo" polish (predictable output naming + run summary logs)
- Expand tests + add CI

### ✅ Definition of Done (Next Milestone)
- One demo command in README that produces a montage from a sample folder
- Clear output location + readable run summary
- `python -m pytest tests/` passes

## ✨ Key Features

- **Automated Hype Detection**: Uses `librosa` HPSS (Harmonic-Percussive Source Separation) to isolate combat sounds from background music/voice.
- **Batch Processing**: Scan entire folders recursively to generate montages from multiple source files.
- **Smart Merging (WIP / In Progress)**: Intelligently merges close-together clips to preserve flow and context — feature is under active tuning and may change.
- **Robust Rendering**: Safely handles video I/O with process isolation and `ffmpeg` concatenation.
- **Configurable**: Fully customizable via CLI flags or YAML configuration files.

## 🚀 Quickstart

### 1. Installation

Requires **Python 3.11+**.

```bash
# Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Verify Setup
Ensure dependencies (including `ffmpeg`) are correctly detected:
```bash
python -m content_ai check
```

### 3. Usage

#### Batch Scan (Recommended)
Scan a folder (and subfolders) for video files and generate a montage.
```bash
python -m content_ai scan --input ./raw_videos --recursive
```

#### Single File
```bash
python -m content_ai scan --input my_gameplay.mp4
```

#### Legacy Mode
The original script is preserved as a wrapper around the new engine:
```bash
python make_reel.py my_gameplay.mp4
```

## ⚙️ Configuration

Defaults are defined in `config/default.yaml`. You can override them using CLI arguments.

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--rms-threshold` | Volume threshold for event detection | `0.10` |
| `--merge-gap` | Merge segments closer than this (seconds) | `2.0` |
| `--padding` | Padding around each event (seconds) | `1.0` |
| `--max-duration` | Max length of final montage | `90s` |
| `--order` | Sorting strategy (`chronological`, `score`, `hybrid`) | `chronological` |

## 📂 Project Structure

```
content-ai/
├── content_ai/          # Core Package
│   ├── cli.py           # Command-line interface
│   ├── config.py        # Config loader
│   ├── detector.py      # Audio analysis logic
│   ├── pipeline.py      # Orchestrator
│   ├── renderer.py      # Video rendering (ffmpeg/moviepy)
│   ├── scanner.py       # File discovery
│   └── segments.py      # Pure logic (merging/clamping)
├── config/
│   └── default.yaml     # Authoritative defaults
├── output/              # Generated runs (run_001, run_002...)
├── tests/               # Unit tests
├── make_reel.py         # Legacy wrapper
└── requirements.txt     # Dependencies
```

## 🛠️ Development

Run tests:
```bash
python -m pytest tests/
```

## ⚠️ Requirements
- **FFmpeg**: Must be available on your system.
  - On Windows/WSL, the tool attempts to use `imageio-ffmpeg` automatically if the system `ffmpeg` is missing.
- **MoviePy 2.x**: This project uses the latest MoviePy v2 API.

## AI/ML Pipeline Transparency (Guidance)
- Audio-first detection: the pipeline prioritizes audio cues (HPSS + RMS) to find percussive events before applying video heuristics.
- HPSS: harmonic/percussive separation is used to enhance percussive events; results depend on `librosa`'s algorithms and source material.
- Event scoring: detected events are assigned scores (energy, prominence, temporal isolation) used for sorting/selection.
- Determinism: processing is mostly deterministic given identical inputs and configs, but external factors (FFmpeg build, thread scheduling) can introduce minor variation.
- Reproducibility: pin dependencies and supply identical input files and `config/default.yaml` to reproduce runs reliably.

## Content-Creation Workflow Expectations
- Clip selection: `detector.py` yields candidate timestamps; `segments.py` applies padding and merge rules to create final clip list.
- Timing: timestamps are derived from audio sample indices and converted to seconds; rounding/trimming may occur to match container frame times.
- Merging (WIP): close events are fused based on `--merge-gap` and scoring heuristics; behavior is being refined to avoid over- or under-merging.
- Rendering: `renderer.py` exports clips and concatenates them via ffmpeg/job isolation to prevent corrupting sources.
- Output layout: runs are stored under `output/run_<NNN>/` with `resolved_config.json`, `segments.json`, and `run_meta.json` for reproducibility.

## Operational Guarantees
- Performance: CPU-bound audio analysis; processing time scales with audio length and sample rate.
- Memory: keep an eye on large inputs — the pipeline processes audio in-memory for accurate HPSS; consider downsampling long files.
- FFmpeg subprocess isolation: the renderer spawns isolated ffmpeg jobs to avoid leaking file descriptors or corrupting the working process.
- Safe file handling: original inputs are never overwritten; outputs are written to new run folders.

## Extensibility Notes
- Add new detectors: implement a detector interface in `detector.py` or add modules and expose them via `cli.py`/`config.py`.
- Add new renderers: `renderer.py` is modular — new backends (direct ffmpeg, cloud renderers) can be plugged in with minimal orchestration changes.
- Config overrides: runtime CLI flags override `config/default.yaml` values; use the `resolved_config.json` in output to capture the exact runtime config.

## Quality & Evaluation
- "Good output": coherent sequence of high-energy clips, minimal dead-air, and natural pacing between segments.
- Tuning: adjust `--rms-threshold`, `--merge-gap`, and `--padding` to match source loudness and desired pacing.
- Logs: the run produces `run_meta.json` and `segments.json` — review these to understand selection and ordering decisions.

