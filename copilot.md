# copilot.md – Architecture Decision Record

**Project:** content-ai
**Last Updated:** 2026-01-07
**Status:** Active Development (Smart Merging phase)

---

## Core Hypothesis: Audio-First Detection

The fundamental design principle is **audio-first** content detection:

1. **HPSS (Harmonic-Percussive Source Separation)** isolates the percussive track
2. **Percussive RMS** energy is computed over sliding windows
3. **Fixed Threshold** detection identifies high-energy events (no adaptive/dynamic thresholding yet)

**Rationale:** Audio signals are more reliable for detecting action/impact moments than visual analysis. Visual methods (OCR, object detection) introduce complexity, latency, and fragility. Audio-first keeps the pipeline fast, deterministic, and robust.

**Non-Negotiable:** Do NOT add visual analysis (OCR/object detection) without explicit project pivot discussion.

---

## Pipeline Architecture: Linear Flow

```
Scan → Detect → Select → Render
```

### 1. Scanner (`scanner.py`)
- Recursively traverses input directory
- Filters by valid extensions (`.mp4`, `.mov`, `.avi`, `.mkv`, etc.)
- Returns list of absolute file paths
- Must be fast and fail gracefully on permission errors

### 2. Detector (`detector.py`)
- Uses librosa HPSS to extract percussive track
- Computes RMS energy over hop windows
- Applies **fixed threshold** to identify event timestamps
- Returns: list of raw event timestamps (floats in seconds)

### 3. Segment Processor (`segments.py`)
**Current Phase: Smart Merging (WIP)**

Transforms raw event timestamps into intelligent, merged segments:

#### Rules:
- **Padding:** Apply pre-roll and post-roll (e.g., ±0.5s) to each event
- **Merge Gap:** If `start_B - end_A < merge_gap`, merge A and B into one segment
- **Max Duration Cap:** Merged segments MUST NOT exceed `max_duration`
  - **Strategy (Preferred):** If merging would exceed max_duration, keep the segment window with highest peak energy (deterministic tie-breaking)
  - Alternative: split intelligently but avoid micro-cuts

#### Edge Cases to Handle:
- Gap exactly at merge_gap boundary
- Overlapping padded events
- Three or more consecutive events within merge_gap
- Segment at video boundaries (start/end clamping)

### 4. Renderer (`renderer.py`)
**Philosophy: Robust Rendering (ffmpeg-first, safety over style)**

- Uses `ffmpeg` subprocess calls for segment extraction
- Hard cuts only (no fancy transitions/effects)
- Concat demuxer for final assembly
- Prioritizes stability: if ffmpeg warns/errors, fail loudly and early
- No audio/video sync tricks – trust ffmpeg defaults

---

## Configuration Strategy

**YAML defaults + CLI overrides**

- Default config: `config/defaults.yaml`
- User can provide custom YAML: `--config user_config.yaml`
- CLI flags take precedence over YAML settings
- All parameters must have sensible defaults for zero-config operation

### Key Parameters:
```yaml
detector:
  rms_threshold: 0.02       # Fixed threshold for percussive energy
  hop_length: 512           # Librosa hop size
  frame_length: 2048        # Librosa frame size

segments:
  pre_roll: 0.5             # Seconds before event
  post_roll: 0.5            # Seconds after event
  merge_gap: 1.0            # Max gap to merge segments
  max_duration: 10.0        # Max length of merged segment

renderer:
  output_format: mp4
  codec: libx264
  audio_codec: aac
```

---

## CLI Design: Noisy and Clear

**Silent failures are unacceptable.**

Every operation must print:
- What it's doing ("Scanning /path/to/videos...")
- Progress indicators (file count, events found)
- Warnings (skipped files, missing audio tracks)
- Success summary (output path, segment count)

### Commands:
```bash
# Full pipeline
python -m content_ai scan /path/to/videos --output highlights.mp4

# One-command demo (milestone target)
python -m content_ai scan --demo
```

---

## One-Command Promise (Next Milestone)

**Contract:**
```bash
python -m content_ai scan --demo
```

**Must deliver:**
1. Use bundled sample asset (small video file in `assets/demo/`) OR synthetic-generated sample
2. Output: `demo_output.mp4` in repo root (or clearly documented path)
3. Exit code 0 on success
4. Print run summary:
   - Files scanned
   - Events detected
   - Segments selected/merged
   - Output path

**Purpose:** Zero-friction validation that the entire pipeline works end-to-end.

---

## Testing Philosophy: Smoke Test Standard

**Do NOT depend on large video files in tests.**

### Preferred Approach:
- **Synthetic audio:** Generate sine waves, white noise, injected percussive spikes
- **Unit tests:** Test each module independently
- **Integration test:** The `--demo` command itself serves as the integration smoke test

### Required Test Coverage:
1. **Scanner:** handles empty dirs, invalid paths, permission errors
2. **Detector:** consistent results on synthetic audio with known peaks
3. **Segments (Smart Merging):**
   - Gap just under/over merge_gap
   - Padding overlap cases
   - Max duration enforcement
   - Deterministic tie-breaking (loudest segment wins)
4. **Renderer:** ffmpeg subprocess handling, concat logic

---

## CI/CD: GitHub Actions

**Minimal, reliable pipeline:**

```yaml
# .github/workflows/ci.yml
- Install dependencies (requirements.txt)
- Run pytest -q
- Lightweight check: ffmpeg --version (or skip gracefully if unavailable)
```

**No heavy assets in CI.** Tests must complete in < 2 minutes.

---

## Current Status & Next Steps

### ✅ Completed:
- Scanner module with recursive traversal
- Detector module with HPSS + RMS threshold
- Basic segment extraction
- CLI structure (`click`-based)
- YAML config loading

### 🚧 In Progress (Smart Merging Phase):
- Finalize `segments.py` with merge logic
- Add max_duration enforcement
- Implement deterministic tie-breaking

### 📋 TODO (This Phase):
1. Complete Smart Merging implementation
2. Add `--demo` flag with bundled sample
3. Write unit tests for segments module
4. Add GitHub Actions CI
5. Update README with Quick Demo section

---

## Design Principles Summary

1. **Audio-First:** Detection is driven by percussive energy, not visual analysis
2. **Fixed Threshold:** Simple, deterministic, predictable (no magic adaptive algorithms yet)
3. **Robust Rendering:** ffmpeg-first, hard cuts, fail loudly on errors
4. **Linear Pipeline:** Scan → Detect → Select → Render (no circular dependencies)
5. **Config Flexibility:** YAML defaults, CLI overrides, sensible zero-config operation
6. **Noisy CLI:** Print everything, silent failures are bugs
7. **Test with Synthetics:** No large video dependencies in unit tests

---

## Operational Rules for AI Agents

**File Generation:**
Do not generate intermediate markdown files (e.g., scratchpads, plans, logs, summaries) on the filesystem. Output your reasoning in the chat or as code comments only. The only markdown files that should exist are: README.md, ARCHITECTURE.md, copilot.md.

**Typing Standards:**
- All functions must have type hints (PEP 484)
- Use Pydantic models for config and data validation
- No `Any` types without justification in comments

**Config Conventions:**
- All config parameters must be defined in `config/default.yaml`
- Pydantic models in `models.py` enforce validation at load time
- CLI overrides take precedence: CLI flags > `config/local.yaml` > `config/default.yaml`
- Never hardcode thresholds or paths in source code

**Adding Pipeline Stages:**
- Detection logic goes in `detector.py` (pure detection, no merging)
- Segment processing goes in `segments.py` (pure functions, no I/O)
- Rendering logic goes in `renderer.py` (FFmpeg/MoviePy only)
- Pipeline orchestration goes in `pipeline.py` (coordinates all stages)
- Never bypass the linear pipeline flow (Scan → Detect → Select → Render)

**Testing Expectations:**
- Unit tests required for all new modules
- Use synthetic data (no large video files in tests)
- Test edge cases: empty inputs, boundary conditions, invalid config
- Coverage target: 80%+ (currently 46%)
- Demo mode (`--demo`) serves as integration smoke test

**Queue System Modifications:**
- Never bypass ACID guarantees (always use atomic transactions)
- State transitions must follow state machine rules (see ARCHITECTURE.md)
- Dirty detection must be deterministic (two-tier hashing)
- Never mark job as succeeded without validating all output files exist
- Heartbeat threads required for jobs >5 minutes

**Documentation Requirements:**
- Architecture decisions go in ARCHITECTURE.md
- User-facing docs go in README.md
- AI/design principles go in copilot.md (this file)
- No duplicate information across files (single source of truth)

---

**This document is the source of truth. When in doubt, refer here.**
