# Robust Rendering System

> **This document is the authoritative source of truth for all rendering decisions in content-ai.**
> All rendering code MUST adhere to the principles and contracts defined herein.

This document describes the video rendering system in content-ai, which provides production-grade FFmpeg orchestration with process isolation, timeout enforcement, and VFR safety.

---

## Epistemological Foundation

### Why This Document Exists

Rendering video is deceptively complex. Silent failures, zombie processes, and audio desync can occur without warning. This document exists to:

1. **Codify knowledge** — Capture hard-won lessons about FFmpeg behavior
2. **Establish invariants** — Define contracts that MUST NOT be violated
3. **Guide decisions** — Provide clear reasoning for every design choice
4. **Prevent regression** — Serve as a checklist for code reviews

### Core Beliefs (Axioms)

These are non-negotiable truths that underpin all rendering decisions:

1. **FFmpeg is a black box** — We cannot trust its internal state. Process isolation is mandatory.
2. **VFR is the enemy** — Variable frame rate sources cause audio desync. Assume all sources are VFR until proven otherwise.
3. **Silence is failure** — Any rendering operation that completes without explicit success verification has failed.
4. **Reproducibility is paramount** — Same inputs + same config MUST produce same outputs.
5. **Timeouts are features** — A process that hangs forever is worse than a process that fails fast.

### Decision Framework

When making rendering decisions, apply this hierarchy:

1. **Safety** — Will this prevent data loss or corruption? (highest priority)
2. **Correctness** — Will this produce accurate output?
3. **Reliability** — Will this work consistently across different inputs?
4. **Performance** — Will this complete in reasonable time? (lowest priority)

Never sacrifice a higher priority for a lower one.

### What "Good" Looks Like

A properly rendered output exhibits these properties:

- **Audio-video sync** — Audio and video remain synchronized throughout
- **Consistent specs** — All segments share identical codec/fps/sample rate
- **No artifacts** — No glitches, freezes, or corruption
- **Deterministic** — Identical inputs produce identical outputs
- **Traceable** — Failures leave enough information to diagnose root cause

---

## Overview

The rendering system addresses common video processing issues:

- **Zombie Processes**: FFmpeg processes that hang indefinitely
- **VFR Audio Desync**: Variable frame rate sources causing audio/video drift
- **Inconsistent Output**: Different codecs/fps across segments causing concat failures
- **Silent Failures**: No visibility into why rendering failed

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Rendering Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Source Video ──► probe_video() ──► VFR Detection              │
│                          │                                       │
│                          ▼                                       │
│                   should_use_fast_path()                        │
│                      │           │                               │
│                      ▼           ▼                               │
│               Fast Path      Re-encode                          │
│              (-c copy)    (contract specs)                      │
│                      │           │                               │
│                      └─────┬─────┘                              │
│                            ▼                                     │
│                    FfmpegRunner.extract_segment()               │
│                            │                                     │
│                            ▼                                     │
│                  validate_segment_compatibility()               │
│                            │                                     │
│                            ▼                                     │
│                    concat_with_runner()                         │
│                            │                                     │
│                            ▼                                     │
│                      Final Montage                              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### FfmpegRunner

The core orchestration class (`src/content_ai/ffmpeg_runner.py`) provides:

```python
from content_ai.ffmpeg_runner import FfmpegRunner, FfmpegProgress

def on_progress(p: FfmpegProgress):
    print(f"Progress: {p.current_time_s:.1f}s @ {p.fps:.0f}fps")

runner = FfmpegRunner(
    global_timeout_s=1800,      # 30 min max
    no_progress_timeout_s=120,  # 2 min stall detection
    progress_callback=on_progress
)

result = runner.extract_segment(
    source_path="input.mp4",
    start=10.0,
    end=20.0,
    output_path="output.mp4",
    codec="libx264",
    preset="medium"
)

if not result.success:
    print(f"Error type: {result.error_type}")
    print(f"Artifacts saved: {result.artifacts_saved}")
```

**Features:**
- Process isolation with `subprocess.Popen`
- Dual timeout enforcement (global + no-progress)
- Real-time progress parsing from FFmpeg stderr
- Cross-platform process tree cleanup (POSIX + Windows)
- Error classification for retry logic (permanent vs transient)
- Artifact preservation on failure (logs + reproducible scripts)

### VFR Detection

Variable Frame Rate detection (`src/content_ai/renderer.py`):

```python
from content_ai.renderer import probe_video, should_use_fast_path

metadata = probe_video("gameplay.mp4")

if metadata.is_vfr:
    print(f"VFR detected! r_frame_rate={metadata.r_frame_rate}, "
          f"avg_frame_rate={metadata.avg_frame_rate}")

# Automatic fast path decision
use_fast = should_use_fast_path(
    metadata,
    force_cfr=True,           # Reject VFR sources
    normalize_to_contract=False
)
```

**How VFR Detection Works:**
1. Use `ffprobe` to extract `r_frame_rate` (declared) and `avg_frame_rate` (actual)
2. Compare the two rates with configurable tolerance (default 1%)
3. If difference > tolerance, mark as VFR

### Render Contract

The render contract (`src/content_ai/models.py`) defines guaranteed output specifications:

```yaml
# config/default.yaml
rendering:
  contract:
    container: "mp4"
    video_codec:
      codec: "libx264"
      profile: "high"
      level: "4.1"
      pixel_format: "yuv420p"
      target_fps: 30
      crf: 23
      preset: "medium"
    audio_codec:
      codec: "aac"
      sample_rate: 48000
      channels: 2
      bitrate: "192k"
```

**Why a Render Contract?**
- Ensures consistent output regardless of source format
- Prevents concat failures from codec mismatches
- Guarantees compatibility with downstream consumers
- Makes debugging easier (known output spec)

## Configuration

### Full Configuration Reference

```yaml
rendering:
  # Render Contract
  contract:
    container: "mp4"
    video_codec:
      codec: "libx264"          # Video codec
      profile: "high"           # H.264 profile (baseline/main/high)
      level: "4.1"              # H.264 level
      pixel_format: "yuv420p"   # Pixel format
      target_fps: 30            # Target FPS (null = preserve source)
      crf: 23                   # Quality (0-51, lower = better)
      preset: "medium"          # Speed preset
    audio_codec:
      codec: "aac"
      sample_rate: 48000
      channels: 2
      bitrate: "192k"

  # Safety Settings
  normalize_to_contract: true   # Always re-encode to contract specs
  validate_before_concat: true  # Validate segment compatibility
  force_cfr: true               # Convert VFR to CFR
  fast_path_enabled: true       # Allow stream copy when safe

  # VFR Detection
  vfr_detection:
    frame_rate_tolerance: 0.01  # 1% tolerance

  # Timeout Enforcement
  global_timeout_s: 1800        # 30 min max
  no_progress_timeout_s: 120    # 2 min stall detection
  max_retries: 2                # Retry transient errors
  kill_grace_period_s: 5        # SIGTERM → SIGKILL grace

  # Debugging
  save_artifacts_on_failure: true
  ffmpeg_loglevel: "info"
  temp_dir: null                # null = worker temp dir
```

### Common Configurations

**Maximum Compatibility (Default):**
```yaml
rendering:
  normalize_to_contract: true
  force_cfr: true
  fast_path_enabled: true
```

**Maximum Speed (CFR Sources Only):**
```yaml
rendering:
  normalize_to_contract: false
  force_cfr: false
  fast_path_enabled: true
```

**Maximum Safety (Always Re-encode):**
```yaml
rendering:
  normalize_to_contract: true
  force_cfr: true
  fast_path_enabled: false
```

## Usage

### Basic Usage

```python
from content_ai.renderer import render_segment_with_runner, concat_with_runner
from content_ai.models import RenderingConfig

# Render segments
config = RenderingConfig()  # Uses defaults

result = render_segment_with_runner(
    "input.mp4", 10.0, 20.0, "clip_000.mp4",
    rendering_config=config
)

if result.success:
    print("Segment rendered successfully")
```

### With Progress Callback

```python
from content_ai.ffmpeg_runner import FfmpegProgress

def on_progress(p: FfmpegProgress):
    if p.total_duration_s > 0:
        pct = (p.current_time_s / p.total_duration_s) * 100
        print(f"Progress: {pct:.1f}% @ {p.fps:.0f}fps, speed={p.speed:.1f}x")

result = render_segment_with_runner(
    "input.mp4", 10.0, 20.0, "output.mp4",
    progress_callback=on_progress
)
```

### Worker Integration

```python
from content_ai.queue.worker import process_video_job

# Enable FfmpegRunner for production
result = process_video_job(
    job=job,
    config=config,
    db_path=db_path,
    run_dir=run_dir,
    use_ffmpeg_runner=True  # Recommended for production
)
```

## Error Handling

### Error Types

```python
from content_ai.ffmpeg_runner import FfmpegErrorType

# Permanent - do not retry
FfmpegErrorType.PERMANENT  # Bad input, codec error, permission denied

# Transient - may retry
FfmpegErrorType.TRANSIENT  # Network timeout, disk I/O stall

# Timeout
FfmpegErrorType.TIMEOUT    # Global or no-progress timeout

# Process killed
FfmpegErrorType.PROCESS_KILLED  # SIGTERM/SIGKILL cleanup
```

### Failure Artifacts

When rendering fails, the system saves:

1. **Error Log** (`ffmpeg_error_{timestamp}.log`):
   - Full command
   - stdout/stderr
   - Timestamp and PID

2. **Reproducible Script** (`ffmpeg_cmd_{timestamp}.sh`):
   - Executable bash script to reproduce the exact command
   - Useful for manual debugging

Location: Worker temp directory or configured `temp_dir`

## Troubleshooting

### VFR Audio Desync

**Symptoms:** Audio drifts out of sync over time

**Cause:** Source video has variable frame rate

**Solution:**
```yaml
rendering:
  force_cfr: true
  normalize_to_contract: true
```

### Zombie FFmpeg Processes

**Symptoms:** FFmpeg processes hang indefinitely, consuming resources

**Solution:** The system automatically enforces timeouts:
- Global timeout: 30 minutes (configurable)
- No-progress timeout: 2 minutes (configurable)
- Process tree cleanup with SIGTERM → SIGKILL

### Concat Failures

**Symptoms:** FFmpeg concat fails with codec mismatch errors

**Cause:** Segments have different codecs/fps/pixel formats

**Solution:**
```yaml
rendering:
  normalize_to_contract: true
  validate_before_concat: true
```

### Slow Rendering

**Symptoms:** Rendering takes too long

**Solutions:**
1. Use faster preset: `preset: "ultrafast"`
2. Enable fast path for compatible sources: `fast_path_enabled: true`
3. Disable normalization for CFR sources: `normalize_to_contract: false`

## Performance Considerations

### Fast Path vs Re-encode

| Mode | Speed | Compatibility | Use When |
|------|-------|---------------|----------|
| Fast Path (`-c copy`) | 10-100x faster | Source must match contract | CFR sources with matching codec |
| Re-encode | Baseline | Always works | VFR sources, codec mismatch |

### Preset Impact

| Preset | Speed | File Size | Quality |
|--------|-------|-----------|---------|
| ultrafast | Fastest | Largest | Good |
| fast | Fast | Large | Good |
| medium | Balanced | Medium | Good |
| slow | Slow | Smaller | Better |
| veryslow | Slowest | Smallest | Best |

Recommendation: Use `medium` for production, `ultrafast` for testing.

## API Reference

### Functions

- `render_segment_with_runner()` - Render segment with FfmpegRunner
- `concat_with_runner()` - Concatenate segments with validation
- `probe_video()` - Extract video metadata with VFR detection
- `should_use_fast_path()` - Determine if stream copy is safe
- `validate_segment_compatibility()` - Check segments before concat

### Classes

- `FfmpegRunner` - Core FFmpeg orchestration
- `FfmpegProgress` - Real-time progress metrics
- `FfmpegResult` - Execution result with error info
- `FfmpegErrorType` - Error classification enum
- `VideoMetadata` - Video metadata from ffprobe
- `RenderingConfig` - Full rendering configuration
- `RenderContractConfig` - Output specification

### Configuration Models

- `VideoCodecConfig` - Video codec settings
- `AudioCodecConfig` - Audio codec settings
- `VFRDetectionConfig` - VFR detection settings

---

## Invariants (MUST NOT Violate)

These are the contracts that all rendering code MUST uphold. Violations should be caught in code review.

### Process Isolation Invariants

1. **Never use `shell=True`** — All FFmpeg commands must use list-based subprocess calls
2. **Always clean up processes** — Every spawned process must be tracked and terminated on failure
3. **Never trust process completion** — Always verify output file exists and has non-zero size
4. **Timeout is mandatory** — No FFmpeg call may run without both global and no-progress timeouts

### Data Integrity Invariants

1. **Never modify source files** — All outputs must be written to new paths
2. **Atomic writes only** — Use temp files + rename for final outputs when possible
3. **Verify before concat** — Never concatenate segments without validation
4. **Preserve artifacts on failure** — Never delete debug info until success confirmed

### VFR Safety Invariants

1. **Probe before fast path** — Never use `-c copy` without confirming CFR
2. **Default to re-encode** — When in doubt, re-encode to contract specs
3. **Compare both frame rates** — VFR detection must compare r_frame_rate AND avg_frame_rate
4. **Tolerance is configurable** — But default must be conservative (1%)

### Error Handling Invariants

1. **Classify all errors** — Every failure must be categorized as permanent or transient
2. **Log before raising** — All errors must be logged with context before propagating
3. **Fail loudly** — Silent failures are bugs; errors must be visible to caller
4. **Include remediation** — Error messages should suggest what to try next

---

## Code Review Checklist

When reviewing rendering code, verify:

- [ ] Process spawning uses `subprocess.Popen` with list args (not `shell=True`)
- [ ] Global timeout is specified and enforced
- [ ] No-progress timeout is specified and enforced
- [ ] Process cleanup handles SIGTERM → wait → SIGKILL sequence
- [ ] Output file existence is verified after FFmpeg completes
- [ ] VFR detection is performed before fast path decision
- [ ] Error classification distinguishes permanent vs transient
- [ ] Failure artifacts are saved with reproducible command
- [ ] No source files are modified
- [ ] Tests cover both success and failure paths

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial robust rendering system with FfmpegRunner, VFR detection, render contract |

---

*This document is maintained alongside the codebase. When rendering behavior changes, update this document first.*
