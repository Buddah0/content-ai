import json
import os
import subprocess
from typing import Any, Dict, List, Optional

import imageio_ffmpeg
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
    # We use a temp filename that includes the video name hash or PID to avoid collisions in parallel (though we are sequential)
    # For simplicity, let's just use a specific temp file and overwrite it, as we process sequentially.
    temp_audio = f"temp_audio_{os.getpid()}.wav"

    try:
        # Load clip just to extract audio
        # explicitly close clip after use
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
            # Adaptive Thresholding
            mean_rms = float(rms.mean())
            std_rms = float(rms.std())
            sensitivity = det_conf.get("sensitivity", 2.5)

            adaptive_thresh = mean_rms + (sensitivity * std_rms)
            # Use max of adaptive or absolute floor (rms_thresh)
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

        # Iterate through audio to find candidate segments

        # CAUTION: we need to know hop_length used in hpss/rms to map back to time
        # librosa.feature.rms uses hop_length=512 by default

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
                        })

        # Handle end of file
        if in_segment:
            seg_dur = times[-1] - start_time
            if seg_dur >= min_dur:
                events.append({
                    "start": start_time,
                    "end": times[-1],
                    "peak": peak_rms,
                })

        # Refine events with Smart Lookback & Flash
        try:
             for ev in events:
                 # 1. Smart Lookback (Audio)
                 start_idx = np.searchsorted(times, ev["start"])

                 smart_start_time = smart_lookback(
                     rms,
                     start_idx,
                     sr=sr,
                     hop_length=512,
                     max_lookback_s=det_conf.get("event_lookback_s", 5.0)
                 )

                 # 2. Flash Detection (Video)
                 flash_time = detect_flash(
                     video_path,
                     smart_start_time,
                     ev["start"]
                 )

                 if flash_time is not None:
                     print(f"Flash detected at {flash_time:.2f}s (Audio start: {smart_start_time:.2f}s)")
                     final_start = min(flash_time, smart_start_time)
                 else:
                     final_start = smart_start_time

                 raw_segments.append({
                     "start": float(final_start),
                     "end": float(ev["end"]),
                     "score": float(ev["peak"]),
                     "video_duration": duration,
                 })

        except Exception as e:
            print(f"Error in refinement step: {e}")
            # Fallback to events as-is
            for ev in events:
                 raw_segments.append({
                     "start": float(max(0.0, ev["start"] - det_conf.get("event_lookback_s", 5.0))),
                     "end": float(ev["end"]),
                     "score": float(ev["peak"]),
                     "video_duration": duration,
                 })

        return raw_segments

    except Exception as e:
        print(f"Error extracting/analyzing {video_path}: {e}")
        return []

    finally:
        # Cleanup temp audio
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

    # Define scan range
    scan_end = event_start_idx
    scan_start = max(0, scan_end - max_lookback_frames)

    if scan_end <= scan_start:
        return 0.0

    # Extract the lookback window
    window = rms[scan_start:scan_end]

    # Find the local minimum (valley) in this window
    # This represents the "quietest" point before the event
    valley_local_idx = np.argmin(window)

    # Calculate global index and time
    final_idx = scan_start + valley_local_idx

    # Safety: ensure we don't return a time AFTER the event start (impossible by def, but good to be sure)
    time_s = librosa.frames_to_time([final_idx], sr=sr, hop_length=hop_length)[0]
    return float(time_s)


def detect_flash(
    video_path: str,
    start_time: float,
    end_time: float,
    threshold_multiplier: float = 1.5,
) -> Optional[float]:
    """
    Scans video frames in [start_time, end_time] for a sudden brightness flash.
    Returns timestamp of flash if found, else None.
    Uses FFmpeg subprocess for fast frame extraction — does not load the full file.
    """
    try:
        if start_time < 0:
            start_time = 0
        if end_time <= start_time:
            return None

        # Get video dimensions via ffprobe (reads only container header, ~1s for any file size)
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_exe = ffmpeg_exe.replace("ffmpeg", "ffprobe")
        if not os.path.exists(ffprobe_exe):
            ffprobe_exe = "ffprobe"

        probe_result = subprocess.run(
            [
                ffprobe_exe, "-v", "quiet", "-print_format", "json",
                "-show_streams", "-select_streams", "v:0", video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        probe_data = json.loads(probe_result.stdout)
        video_streams = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"]
        if not video_streams:
            return None
        vs = video_streams[0]
        width = int(vs["width"])
        height = int(vs["height"])

        # Extract raw RGB24 frames from the window only — fast seek, no full-file decode
        frame_size = width * height * 3
        proc = subprocess.Popen(
            [
                ffmpeg_exe,
                "-ss", str(start_time),
                "-t", str(end_time - start_time),
                "-i", video_path,
                "-vf", "fps=10",
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "-an",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        times_list = []
        brightness = []
        frame_index = 0

        while True:
            chunk = proc.stdout.read(frame_size)
            if len(chunk) < frame_size:
                break
            avg = float(np.mean(np.frombuffer(chunk, dtype=np.uint8)))
            times_list.append(start_time + frame_index / 10.0)
            brightness.append(avg)
            frame_index += 1

        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            return None

        if not brightness:
            return None

        brightness = np.array(brightness)
        mean_b = np.mean(brightness)
        std_b = np.std(brightness)
        max_idx = int(np.argmax(brightness))
        max_val = brightness[max_idx]

        if max_val > mean_b + (threshold_multiplier * std_b) and max_val > 50:
            return float(times_list[max_idx])

        return None

    except Exception as e:
        print(f"Flash detection error: {e}")
        return None

