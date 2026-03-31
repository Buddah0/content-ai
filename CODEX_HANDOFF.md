# Codex Handoff: Fix Lookback Hype Feature

## Context

You are continuing work on **Content AI** — an audio-first highlight detection system for gameplay footage.
Branch: `Improving-look-back-and-hype`

The "lookback hype" feature extends a detected audio segment **backward** to capture the build-up context before a loud spike (e.g., footsteps + tension before an explosion). The current implementation was just upgraded from a naive fixed-window approach to a two-stage "smart" system, but has several bugs.

---

## What the Feature Should Do

1. **Audio detection** finds a high-energy percussive event (e.g., explosion at t=10s) using HPSS + RMS thresholding.
2. **Smart Lookback (Audio)**: Scan backward up to `event_lookback_s` (default 5s) from the event start to find the **minimum RMS valley** — the "quiet before the storm" (e.g., t=7s).
3. **Flash Detection (Video)**: Optionally find a sudden brightness spike in the video that coincides with the action start (e.g., camera flash).
4. Final segment start = `min(flash_time, audio_valley_time)`.

### Example

```
RMS:  [0.05 0.05 0.05 0.05 0.05 0.05 0.05 0.01 0.02 0.15 0.50 0.30 0.05 ...]
time:  0    1    2    3    4    5    6    7    8    9    10   11   12  ...
                                             ^valley        ^peak
```
- Detection triggers at ~t=9 (first frame > threshold 0.1).
- Fixed 5s lookback → goes to t=4 (irrelevant background).
- **Smart lookback → finds valley at t=7 (minimum in [4,9] window). ✓**

---

## Key Files

| File | Role |
|------|------|
| `src/content_ai/detector.py` | Main detection logic — `detect_hype()`, `smart_lookback()`, `detect_flash()` |
| `tests/test_detector.py` | Unit tests (currently failing / incomplete) |
| `tests/reproduce_lookback.py` | Standalone debug script for smart_lookback() |
| `src/content_ai/models.py` | Pydantic config schema (`DetectionConfig.event_lookback_s`) |
| `src/content_ai/segments.py` | Post-processing (merge, pad, clamp) — called after `detect_hype()` |

---

## Current Code (Full)

### `src/content_ai/detector.py`

```python
import os
from typing import Any, Dict, List


import librosa
import numpy as np
from moviepy.editor import VideoFileClip



def detect_hype(video_path: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Run HPSS + RMS detection on a video file.

    Returns:
        List of raw segments (unmerged, unpadded) with metadata.
    """
    # Config keys
    det_conf = config.get("detection", {})
    rms_thresh = det_conf.get("rms_threshold", 0.10)
    min_dur = det_conf.get("min_event_duration_s", 0.1)
    margin = det_conf.get("hpss_margin", [1.0, 5.0])
    # Ensure margin is tuple
    if isinstance(margin, list):
        margin = tuple(margin)

    # 1. Extract Audio
    temp_audio = f"temp_audio_{os.getpid()}.wav"

    try:
        with VideoFileClip(video_path) as clip:
            if clip.audio is None:
                print(f"Warning: No audio in {video_path}")
                return []
            clip.audio.write_audiofile(temp_audio, logger=None)
            duration = clip.duration

        # 2. Analyze
        y, sr = librosa.load(temp_audio)
        y_harmonic, y_percussive = librosa.effects.hpss(y, margin=margin)
        rms = librosa.feature.rms(y=y_percussive)[0]
        times = librosa.times_like(rms, sr=sr)

        if det_conf.get("adaptive_threshold", True):
            mean_rms = float(rms.mean())
            std_rms = float(rms.std())
            sensitivity = det_conf.get("sensitivity", 2.5)
            adaptive_thresh = mean_rms + (sensitivity * std_rms)
            final_thresh = max(adaptive_thresh, rms_thresh)
            print(f"Adaptive Stats :: Mean: {mean_rms:.4f}, Std: {std_rms:.4f}, K: {sensitivity}")
            print(
                f"Threshold :: Adaptive: {adaptive_thresh:.4f} vs Floor: {rms_thresh} -> Final: {final_thresh:.4f}"
            )
        else:
            final_thresh = rms_thresh

        hype_mask = rms > final_thresh

        # 3. Collect Raw Segments
        raw_segments = []
        in_segment = False
        start_time = 0.0
        peak_rms = 0.0

        hop_length = 512  # Librosa default

        events = []

        for i, is_hype in enumerate(hype_mask):
            t = times[i]
            val = rms[i]

            if is_hype:
                if not in_segment:
                    in_segment = True
                    start_time = t
                    peak_rms = val
                else:
                    peak_rms = max(peak_rms, val)
            else:
                if in_segment:
                    in_segment = False
                    seg_dur = t - start_time
                    if seg_dur >= min_dur:
                        events.append({
                            "start": start_time,
                            "end": t,
                            "peak": peak_rms,
                            "start_idx": i  # BUG: i is the first non-hype frame (end), not the start
                        })

        # Handle end of file
        if in_segment:
            seg_dur = times[-1] - start_time
            if seg_dur >= min_dur:
                events.append({
                    "start": start_time,
                    "end": times[-1],
                    "peak": peak_rms,
                    "start_idx": len(times)-1
                })

        # Refine events with Smart Lookback & Flash
        try:
             video_clip = VideoFileClip(video_path)

             for ev in events:
                 # Find index corresponding to event start
                 start_idx = np.searchsorted(times, ev["start"])

                 smart_start_time = smart_lookback(
                     rms,
                     start_idx,
                     sr=sr,
                     hop_length=512,
                     max_lookback_s=det_conf.get("event_lookback_s", 5.0)
                 )

                 # Flash Detection: search from smart_start up to event end
                 flash_time = detect_flash(
                     video_clip,
                     smart_start_time,
                     ev["end"]
                 )

                 if flash_time is not None:
                     print(f"Flash detected at {flash_time:.2f}s (Audio start: {smart_start_time:.2f}s)")
                     final_start = min(flash_time, smart_start_time)
                     final_start = max(0.0, final_start - 0.5)  # hardcoded 0.5s pre-roll
                 else:
                     final_start = smart_start_time

                 raw_segments.append({
                     "start": float(final_start),
                     "end": float(ev["end"]),
                     "score": float(ev["peak"]),
                     "video_duration": duration,
                 })

             video_clip.close()

        except Exception as e:
            print(f"Error in refinement step: {e}")
            # Fallback: BUG - can produce negative start times
            for ev in events:
                 raw_segments.append({
                     "start": float(ev["start"] - det_conf.get("event_lookback_s", 5.0)),
                     "end": float(ev["end"]),
                     "score": float(ev["peak"]),
                     "video_duration": duration,
                 })

        return raw_segments

    except Exception as e:
        print(f"Error extracting/analyzing {video_path}: {e}")
        return []

    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass


def smart_lookback(
    rms: np.ndarray,
    event_start_idx: int,
    sr: int,
    hop_length: int,
    min_event_duration_s: float = 0.5,
    max_lookback_s: float = 10.0,
) -> float:
    """
    Scans backwards from event_start_idx to find the 'true' start of the action.
    Target: Find the start of the 'swell' or 'spike' that led to the event.
    """
    fps_audio = sr / hop_length
    max_lookback_frames = int(max_lookback_s * fps_audio)

    scan_end = event_start_idx
    scan_start = max(0, scan_end - max_lookback_frames)

    if scan_end <= scan_start:
        return 0.0

    window = rms[scan_start:scan_end]

    # Find the local minimum (valley) — the "quietest" point before the event
    valley_local_idx = np.argmin(window)

    final_idx = scan_start + valley_local_idx

    time_s = librosa.frames_to_time([final_idx], sr=sr, hop_length=hop_length)[0]
    return float(time_s)


def detect_flash(
    clip: VideoFileClip,
    start_time: float,
    end_time: float,
    threshold_multiplier: float = 1.5,
) -> float:  # BUG: return type should be Optional[float]
    """
    Scans video frames in [start_time, end_time] for a sudden brightness flash.
    Returns timestamp of flash if found, else None.
    """
    try:
        if start_time < 0: start_time = 0
        if float(end_time) > float(clip.duration): end_time = float(clip.duration)
        if float(end_time) <= float(start_time): return None

        times = []
        brightness = []

        for t, frame in clip.subclip(start_time, end_time).iter_frames(fps=10, with_times=True, dtype="uint8"):
            avg = np.mean(frame)
            times.append(start_time + t)
            brightness.append(avg)

        if not brightness:
            return None

        brightness = np.array(brightness)
        mean_b = np.mean(brightness)
        std_b = np.std(brightness)

        max_idx = np.argmax(brightness)
        max_val = brightness[max_idx]

        if max_val > mean_b + (threshold_multiplier * std_b) and max_val > 50:
             return float(times[max_idx])

        return None

    except Exception as e:
        print(f"Flash detection error: {e}")
        return None
```

---

### `tests/test_detector.py`

```python
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from content_ai import detector


@pytest.fixture
def mock_librosa():
    with patch("content_ai.detector.librosa") as mock:
        yield mock


@pytest.fixture
def mock_video_clip():
    with patch("content_ai.detector.VideoFileClip") as mock:
        mock_instance = mock.return_value.__enter__.return_value
        mock_instance.audio = MagicMock()
        mock_instance.duration = 10.0
        yield mock_instance
        # BUG: mock.return_value.duration is NOT set to 10.0
        # detect_flash calls float(clip.duration) on the non-context-manager instance
        # which is mock.return_value, not mock.return_value.__enter__.return_value


def test_adaptive_threshold(mock_librosa, mock_video_clip):
    y = np.random.rand(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    rms_vals = np.ones(100) * 0.05
    rms_vals[50] = 0.5

    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = np.linspace(0, 10, 100)

    config = {"detection": {"adaptive_threshold": True, "sensitivity": 2.0, "rms_threshold": 0.1}}

    segments = detector.detect_hype("dummy.mp4", config)

    assert len(segments) >= 1

    config["detection"]["sensitivity"] = 100.0
    segments_strict = detector.detect_hype("dummy.mp4", config)
    assert len(segments_strict) == 0


def test_event_lookback(mock_librosa, mock_video_clip):
    y = np.zeros(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    rms_vals = np.ones(20) * 0.05
    rms_vals[7] = 0.01             # Quiet valley at t=7
    rms_vals[8] = 0.02
    rms_vals[9] = 0.15             # Rising (triggers hype)
    rms_vals[10] = 0.5             # Event peak
    rms_vals[11] = 0.3             # Decaying

    # NOTE: uses detector.librosa (same mock as mock_librosa, but inconsistent style)
    detector.librosa.feature.rms.return_value = np.array([rms_vals])
    times = np.arange(20, dtype=float)
    detector.librosa.times_like.return_value = times

    # Mock frames_to_time for smart_lookback
    detector.librosa.frames_to_time.side_effect = lambda indices, sr, hop_length: np.array(
        [times[i] if i < len(times) else times[-1] for i in indices]
    )

    config = {
        "detection": {"adaptive_threshold": False, "rms_threshold": 0.1, "event_lookback_s": 5.0}
    }

    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) >= 1
    # Smart lookback should find the valley at t=7 (minimum in the lookback window)
    assert segments[0]["start"] == 7.0
    assert segments[0]["end"] == 12.0  # First non-hype frame after index 11

    # --- Second sub-test: nothing detected ---
    y = np.zeros(100)
    sr = 22050
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.effects.hpss.return_value = (y, y)

    rms_vals = np.ones(100) * 0.05
    mock_librosa.feature.rms.return_value = np.array([rms_vals])
    mock_librosa.times_like.return_value = np.linspace(0, 10, 100)

    config = {"detection": {"adaptive_threshold": False, "rms_threshold": 0.1}}

    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) == 0

    config["detection"]["rms_threshold"] = 0.01
    segments = detector.detect_hype("dummy.mp4", config)
    assert len(segments) > 0
```

---

### `tests/reproduce_lookback.py`

```python
import numpy as np


def smart_lookback(
    rms: np.ndarray,
    event_start_idx: int,
    sr: int,
    hop_length: int,
    min_event_duration_s: float = 0.5,
    max_lookback_s: float = 10.0,
) -> float:
    """
    Scans backwards from event_start_idx to find the 'true' start of the action.
    """
    fps_audio = sr / hop_length
    max_lookback_frames = int(max_lookback_s * fps_audio)
    min_event_frames = int(min_event_duration_s * fps_audio)

    scan_end = event_start_idx
    scan_start = max(0, scan_end - max_lookback_frames)

    if scan_end <= scan_start:
        return 0.0

    window = rms[scan_start:scan_end]
    window_rev = window[::-1]

    trigger_level = rms[event_start_idx]
    cutoff_idx = 0

    curr_min = window_rev[0]
    curr_min_idx = 0

    for i in range(len(window_rev)):
        val = window_rev[i]
        if val < curr_min:
            curr_min = val
            curr_min_idx = i
        pass  # dead loop — never used

    valley_idx = np.argmin(window)  # Better approach used here

    final_idx = scan_start + valley_idx

    # BUG: librosa not imported at module level — only inside __main__
    time_s = librosa.frames_to_time([final_idx], sr=sr, hop_length=hop_length)[0]
    return float(time_s)


def create_synthetic_audio(sr=22050, duration=30):
    t = np.linspace(0, duration, duration * 10)
    rms = np.random.normal(0.05, 0.01, len(t))
    rms[80:90] = 0.01          # Quiet before storm (8-9s)
    rms[90:100] = np.linspace(0.01, 0.8, 10)  # Build up (9-10s)
    rms[100:120] = 0.8 + np.random.normal(0, 0.05, 20)  # Event peak (10-12s)
    rms[120:130] = np.linspace(0.8, 0.05, 10)  # Decay
    return t, rms


if __name__ == "__main__":
    import librosa

    sr = 22050
    hop = 2205  # 10 fps

    print("Generating synthetic data...")
    t, rms = create_synthetic_audio()
    rms = np.abs(rms)

    event_start_idx = 100  # t=10s
    print(f"Event Triggered at: {t[event_start_idx]:.2f}s (RMS={rms[event_start_idx]:.2f})")

    fixed_time = t[event_start_idx] - 5.0
    print(f"Fixed Lookback (5s): {fixed_time:.2f}s")

    smart_time = smart_lookback(rms, event_start_idx, sr, hop, max_lookback_s=5.0)
    print(f"Smart Lookback:      {smart_time:.2f}s")

    print("-" * 30)
    print(f"Actual 'Quiet' start was around 8.0s.")
    print(f"Fixed went to 5.0s (too far, unrelated background).")
    print(f"Smart went to {smart_time:.2f}s (should be close to 8.0s or 9.0s).")
```

---

### `src/content_ai/models.py` (relevant section)

```python
class DetectionConfig(BaseModel):
    rms_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
    min_event_duration_s: float = Field(default=0.1, gt=0.0)
    hpss_margin: tuple[float, float] = Field(default=(1.0, 5.0))
    adaptive_threshold: bool = Field(default=True)
    sensitivity: float = Field(default=2.5, ge=0.0)
    event_lookback_s: float = Field(
        default=5.0, ge=0.0,
        description="Seconds to look back from the start of an event (captures build-up)",
    )
```

---

## Known Bugs to Fix

### Bug 1: `detect_hype()` — `start_idx` is dead code (minor)
**File**: `detector.py:104`
`"start_idx": i` stores the END-of-segment index (first non-hype frame), not the start. However, this value is **never used** — the refinement loop correctly recomputes the start index via `np.searchsorted(times, ev["start"])` on line 131. The dead field should be removed for clarity.

### Bug 2: `detect_hype()` — fallback produces negative start times
**File**: `detector.py:178`
```python
"start": float(ev["start"] - det_conf.get("event_lookback_s", 5.0)),
```
If `ev["start"] = 2.0` and `event_lookback_s = 5.0`, this produces `start = -3.0` (invalid).
**Fix**: Clamp with `max(0.0, ...)`.

### Bug 3: `detect_flash()` — wrong scan window
**File**: `detector.py:148`
Flash detection searches from `smart_start_time` to `ev["end"]` (end of entire event). The flash (if any) would be at the start of the action, not the end. It should scan from `smart_start_time` to `ev["start"]` (the original detection trigger point).

### Bug 4: `detect_flash()` — return type annotation is wrong
**File**: `detector.py:241`
Declared as `-> float` but returns `None` when no flash. Should be `-> Optional[float]`.

### Bug 5: `mock_video_clip` fixture — non-context-manager `VideoFileClip` not mocked
**File**: `tests/test_detector.py:17-21`
The fixture sets `duration=10.0` on `mock.return_value.__enter__.return_value` (used for audio extraction). But the refinement step calls `VideoFileClip(video_path)` **without** a context manager, getting `mock.return_value` — which has `duration` as a bare `MagicMock`. This causes `float(clip.duration)` in `detect_flash()` to raise `TypeError`, silently caught and returning `None`. The test passes only by accident.
**Fix**: Also set `mock.return_value.duration = 10.0` in the fixture (and configure `subclip().iter_frames()` to return `[]`).

### Bug 6: `test_event_lookback` — uses `detector.librosa` inconsistently
**File**: `tests/test_detector.py:76-83`
Uses `detector.librosa` directly instead of the `mock_librosa` fixture parameter. While they reference the same mock object (both point to `content_ai.detector.librosa`), this is confusing. Should use `mock_librosa` consistently.

### Bug 7: `reproduce_lookback.py` — `librosa` not imported in `smart_lookback()`
**File**: `tests/reproduce_lookback.py:112`
```python
time_s = librosa.frames_to_time([final_idx], sr=sr, hop_length=hop_length)[0]
```
`librosa` is only imported inside `if __name__ == "__main__":`. Calling `smart_lookback()` from any other module/test would `NameError`. The function should either accept time conversion as input (passing `times` array) or import librosa at the top of the file.

### Bug 8: `reproduce_lookback.py` — dead iterative loop
**File**: `tests/reproduce_lookback.py:68-91`
The `for i in range(len(window_rev)):` loop (lines 73-91) sets `curr_min` and `curr_min_idx` but those variables are never used — the function ignores them and falls through to `np.argmin(window)`. This dead code should be removed.

---

## What Needs to Be Done

1. **Fix `detector.py`**:
   - Remove dead `start_idx` from `events` dict (or fix to store actual start index)
   - Fix fallback: `max(0.0, ev["start"] - det_conf.get("event_lookback_s", 5.0))`
   - Fix flash scan window: scan to `ev["start"]` not `ev["end"]`
   - Fix return type annotation on `detect_flash` to `Optional[float]`
   - Remove hardcoded `0.5` pre-roll on flash — either make it configurable or remove

2. **Fix `tests/test_detector.py`**:
   - Update `mock_video_clip` fixture to also set `mock.return_value.duration = 10.0`
   - Configure `mock.return_value.subclip.return_value.iter_frames.return_value = []` so flash detection cleanly returns `None`
   - Use `mock_librosa` consistently in `test_event_lookback` instead of `detector.librosa`
   - Make `test_event_lookback` more explicit about why smart_lookback returns t=7.0

3. **Fix `tests/reproduce_lookback.py`**:
   - Add `import librosa` at top of file (or refactor to avoid needing it)
   - Remove the dead iterative loop (lines 68-91)
   - Optionally simplify to just show the working valley-finding logic

---

## How to Run Tests

```bash
cd /home/buddah/projects/content-ai
python -m pytest tests/test_detector.py -v
```

To run the reproduce script standalone:
```bash
python tests/reproduce_lookback.py
```
Expected output:
```
Event Triggered at: 10.00s (RMS=0.80)
Fixed Lookback (5s): 5.00s
Smart Lookback:      ~8.00s  ← should be close to the quiet valley at 8-9s
```

---

## Design Intent

The overall flow after fixes:

```
detect_hype(video_path, config)
  │
  ├─ Extract audio → RMS on percussive track
  ├─ Adaptive or fixed threshold → hype_mask
  ├─ Collect raw events (start_time, end_time, peak_rms)
  │
  └─ For each event:
       ├─ smart_lookback(rms, event_start_idx, ...) → audio_valley_time
       ├─ detect_flash(video_clip, audio_valley_time, event_start_time) → flash_time or None
       ├─ final_start = min(flash_time, audio_valley_time) if flash else audio_valley_time
       └─ Append {start: final_start, end: event_end, score: peak_rms}
```

The pipeline (`pipeline.py`) then calls `pad_segments()`, `merge_segments()`, `clamp_segments()` on the result.
