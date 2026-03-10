import os
from typing import Any, Dict, List, Optional


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

        # We need the clip object for flash detection if we want to use it
        # But we closed it above. 
        # Re-opening strictly for flash detection on candidate segments is better than holding it open?
        # PREV CODE closed it. We can reopen if needed.
        
        # Iterate through audio to find candidate segments
        hop_length = 512 # Librosa default 
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
        # We need to reopen clip for flash detection
        try:
             video_clip = VideoFileClip(video_path)
             
             for ev in events:
                 # 1. Smart Lookback (Audio)
                 # Find the index corresponding to event start
                 # times array maps index -> time. 
                 # We want index for ev["start"]
                 # simple search or calc? index ~ time * sr / hop
                 # But we have `times` array.
                 # Let's find index where times >= start
                 start_idx = np.searchsorted(times, ev["start"])
                 
                 smart_start_time = smart_lookback(
                     rms, 
                     start_idx, 
                     sr=sr, 
                     hop_length=512, 
                     max_lookback_s=det_conf.get("event_lookback_s", 5.0)
                 )
                 
                 # 2. Flash Detection (Video)
                 # Search for flash in the window [smart_start_time, ev["start"]]
                 # or even slightly before smart_start? 
                 # Let's search from smart_start up to the event peak.
                 flash_time = detect_flash(
                     video_clip, 
                     smart_start_time, 
                     ev["start"]
                 )
                 
                 # Decide final start
                 # If flash found and is earlier/valid, use it?
                 if flash_time is not None:
                     # If flash is within reasonable range of audio start
                     print(f"Flash detected at {flash_time:.2f}s (Audio start: {smart_start_time:.2f}s)")
                     # Use the earlier of the two, but don't go back ridiculous amount?
                     # Flash is usually THE start.
                     final_start = min(flash_time, smart_start_time)
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
    clip: VideoFileClip,
    start_time: float,
    end_time: float,
    threshold_multiplier: float = 1.5,
) -> Optional[float]:
    """
    Scans video frames in [start_time, end_time] for a sudden brightness flash.
    Returns timestamp of flash if found, else None.
    """
    try:
        # Extract subclip to avoid processing entire video
        # Safety clamp
        if start_time < 0: start_time = 0
        if float(end_time) > float(clip.duration): end_time = float(clip.duration)
        if float(end_time) <= float(start_time): return None

        # Sample at 10fps for speed
        # We look for a localized spike in brightness
        
        # Generator of frames
        times = []
        brightness = []
        
        for t, frame in clip.subclip(start_time, end_time).iter_frames(fps=10, with_times=True, dtype="uint8"):
            # Simple brightness: mean of RGB
            # Frame is HxWx3
            avg = np.mean(frame)
            times.append(start_time + t) # t is relative to subclip start
            brightness.append(avg)

        if not brightness:
            return None

        brightness = np.array(brightness)
        mean_b = np.mean(brightness)
        std_b = np.std(brightness)
        
        # Detect spike
        # If max brightness is significantly higher than mean
        max_idx = np.argmax(brightness)
        max_val = brightness[max_idx]
        
        if max_val > mean_b + (threshold_multiplier * std_b) and max_val > 50: # absolute floor
             return float(times[max_idx])

        return None

    except Exception as e:
        print(f"Flash detection error: {e}")
        return None

