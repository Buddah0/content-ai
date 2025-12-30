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

Folder Scanning Architecture (Next Milestone)
-------------------------------------------
Goal: support both CLI batch mode and config-driven runs.

Design
- CLI: `content-ai scan --input path --output out --recursive [flags]` (planned)
- Config-driven: `content-ai run --config config/default.yaml` (planned)
- Precedence: CLI flags > `config/local.yaml` (user) > `config/default.yaml`.
- Output: each run creates `output/run_###/` with artifacts.

run_meta.json (DIFF-ONLY design)
- Store `defaults_version` from `config/default.yaml`.
- Store only values that differ from defaults (CLI or local override values).
- Store resolved input list and produced outputs.

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
