AI gameplay highlight detector + montage builder

Content AI — style-aware editing for gameplay highlights.

Project Status
- Local repo; not yet published to GitHub. Basic engine exists for detecting percussive "hype" moments and stitching them into a montage. Next milestone: folder scanning (batch processing) and a CLI.

What it does (Current)
- Uses HPSS via librosa to separate harmonic (voice/music) and percussive (shots/explosions) elements.
- Calculates RMS on the percussive layer to detect events.
- Smart edit logic (thresholding, micro-burst detection, padding, merging/bridging) implemented in `make_reel.py`.
- Video export via moviepy.

Style Replication Vision (Planned)
- Learn editing patterns (pacing, cut density, padding, merge gaps, ranking) from pairs of (RAW gameplay, FINAL montage).
- Option 1 inputs: a pair of (raw gameplay video, final edited montage).
- Planned pipeline (high level):
  - detect cuts in the final montage (cut_detector) — Planned
  - align montage segments back to raw timeline (aligner) — Planned
  - extract style features and save a `style_profile` (JSON) — Planned
  - apply `style_profile` to future reels via `style_applier` — Planned

Quickstart
1) Create a virtualenv and activate it:

```bash
python3.11 -m venv venv
source venv/bin/activate
```

2) Install dependencies (minimum):

```bash
pip install numpy librosa moviepy
# You will also need ffmpeg installed on your system for moviepy to write video files.
```

3) Run the simple demo entrypoints (existing scripts):

```bash
python make_reel.py            # produces hype_reel.mp4 from my_gameplay.mp4 (default)
python find_hype.py           # prints detected percussive segments
python find_hype_strict.py    # prints volume report / percussive peaks
```

Folder Scanning (Next Milestone) — Planned
- Two modes (planned):
  1) CLI batch mode: scan a folder (optional recursive), filter by extensions, write run-based outputs.
  2) Config-driven mode: use [config/default.yaml](config/default.yaml) as defaults, allow `--config` to override.
- Precedence: CLI flags will override config values.
- Example (planned):

```bash
# CLI batch (planned)
content-ai scan --input ./raw_videos --output ./output --recursive --limit 10

# Config-driven (planned)
content-ai run --config config/default.yaml
```

Run-based output structure
- Each run produces `output/run_###/` containing:
  - `montage.mp4` (final video)
  - `segments.json` (detected segments) — if generated
  - `run_meta.json` (DIFF-ONLY metadata with `defaults_version` and overrides)

Configuration / Defaults
- The authoritative defaults live in [config/default.yaml](config/default.yaml).
- Key defaults:
  - `rms_threshold`: 0.10
  - `min_event_duration_s`: 0.1
  - `context_padding_s`: 1.0
  - `merge_gap_s`: 2.0
- Per-user overrides should be placed in `config/local.yaml` (planned) and will be ignored by git.

Outputs / Artifacts
- Exports go to `output/` by default (see config for overrides).
- Intermediate artifacts (extracted audio, .wav files, .npy arrays) are produced into `output/run_###/` or temporary files like `temp_audio.wav`.

Repo Structure (current)
```
find_hype.py           # utility: detect percussive hype moments (uses librosa)
find_hype_strict.py    # stricter analysis & volume report
make_reel.py           # main quick demo that writes hype_reel.mp4
my_gameplay.mp4        # sample gameplay file (local)
hype_reel.mp4          # sample output (local)
temp_audio.wav         # temp audio extracted by scripts
venv/                  # local virtualenv (ignored by git)
```

Git + Branching (local)
```bash
git init
git add .
git commit -m "chore: initial local repo"
git branch -M main

# Recommended feature branches
git checkout -b feat/folder-scan
git checkout -b feat/style-profile
git checkout -b chore/docs
```

Roadmap (realistic)
- Folder scanning + batch processing (CLI + config)
- Adaptive thresholding (median + MAD)
- Audio normalization and multi-feature fusion
- Cooldown / debounce logic to avoid overcutting
- OCR killfeed confirmation (experimental)
- Style learning pipeline (Option 1)

If something above is labeled "Planned", it is not yet implemented — see the roadmap and ARCHITECTURE.md for details.
