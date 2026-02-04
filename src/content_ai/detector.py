import os
from typing import Any, Dict, List

import librosa
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
            print(f"Threshold :: Adaptive: {adaptive_thresh:.4f} vs Floor: {rms_thresh} -> Final: {final_thresh:.4f}")
        else:
            final_thresh = rms_thresh

        hype_mask = rms > final_thresh

        # 3. Collect Raw Segments
        raw_segments = []
        in_segment = False
        start_time = 0.0
        peak_rms = 0.0

        for i, is_hype in enumerate(hype_mask):
            t = times[i]
            val = rms[i]

            # Retrieve configurable lookback (default 5s)
            lookback_s = det_conf.get("event_lookback_s", 5.0)

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
                        # Apply lookback here to capture context *before* the hype event
                        adj_start = max(0.0, start_time - lookback_s)
                        
                        raw_segments.append(
                            {
                                "start": float(adj_start),
                                # We extend end slightly? No, end is end of hype. 
                                # Often the hype continues (cheers), so end is fine.
                                "end": float(t),
                                "score": float(peak_rms),
                                "video_duration": duration,
                            }
                        )

        # Handle end of file
        if in_segment:
            seg_dur = times[-1] - start_time
            if seg_dur >= min_dur:
                adj_start = max(0.0, start_time - det_conf.get("event_lookback_s", 5.0))
                raw_segments.append(
                    {
                        "start": float(adj_start),
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
            except Exception:
                pass
