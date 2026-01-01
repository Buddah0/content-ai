# Content AI

**Content AI** is an intelligent engine that automatically turns raw gameplay footage into rhythmic "hype montages." It uses audio signal processing to detect percussive events (gunshots, explosions, critical hits) and stitches them together into a high-energy reel.

## ✨ Key Features

- **Automated Hype Detection**: Uses `librosa` HPSS (Harmonic-Percussive Source Separation) to isolate combat sounds from background music/voice.
- **Batch Processing**: Scan entire folders recursively to generate montages from multiple source files.
- **Smart Merging**: Intelligently merges close-together clips to preserve flow and context.
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
