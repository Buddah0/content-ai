import librosa
import numpy as np
import os
from moviepy import VideoFileClip
from typing import List, Dict, Any, Tuple
from pathlib import Path


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

        hype_mask = rms > rms_thresh

        # 3. Collect Raw Segments
        raw_segments = []
        in_segment = False
        start_time = 0.0
        peak_rms = 0.0

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
                        raw_segments.append(
                            {
                                "start": float(start_time),
                                "end": float(t),
                                "score": float(peak_rms),
                                "video_duration": duration,
                            }
                        )

        # Handle end of file
        if in_segment:
            seg_dur = times[-1] - start_time
            if seg_dur >= min_dur:
                raw_segments.append(
                    {
                        "start": float(start_time),
                        "end": float(times[-1]),
                        "score": float(peak_rms),
                        "video_duration": duration,
                    }
                )

        return raw_segments

    except Exception as e:
        print(f"Error extracting/analyzing {video_path}: {e}")
        return []

    finally:
        # Cleanup temp audio
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except:
                pass
