
import librosa
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
    Target: Find the start of the 'swell' or 'spike' that led to the event.
    Finds the local minimum (valley) in the lookback window.
    """
    
    # Constants
    fps_audio = sr / hop_length
    max_lookback_frames = int(max_lookback_s * fps_audio)
    min_event_frames = int(min_event_duration_s * fps_audio)
    
    # 1. Define scan range
    scan_end = event_start_idx
    scan_start = max(0, scan_end - max_lookback_frames)
    
    if scan_end <= scan_start:
        return 0.0

    # Extract the lookback window
    window = rms[scan_start:scan_end]
    valley_idx = np.argmin(window)
    
    final_idx = scan_start + valley_idx

    time_s = librosa.frames_to_time([final_idx], sr=sr, hop_length=hop_length)[0]
    return float(time_s)

def create_synthetic_audio(sr=22050, duration=30):
    """
    Creates synthetic RMS array with:
    - Background noise (0.05)
    - A 'Quiet' moment (0.01)
    - A 'Build up' (linear rise)
    - A 'Spike' / Event (0.8)
    - Decay
    """
    t = np.linspace(0, duration, duration * 10) # 10 fps usually sufficient for RMS
    rms = np.random.normal(0.05, 0.01, len(t))
    
    # Event 1 at 10s
    # Quiet before storm at 8s-9s
    rms[80:90] = 0.01 
    # Build up 9s-10s
    rms[90:100] = np.linspace(0.01, 0.8, 10)
    # Event sustain 10s-12s
    rms[100:120] = 0.8 + np.random.normal(0, 0.05, 20)
    # Decay
    rms[120:130] = np.linspace(0.8, 0.05, 10)
    
    return t, rms

if __name__ == "__main__":

    sr = 22050
    hop = 2205 # 10 fps
    
    print("Generating synthetic data...")
    t, rms = create_synthetic_audio()
    rms = np.abs(rms) # Ensure positive
    
    # Assume detection triggered at t=10.0s (index 100)
    event_start_idx = 100
    print(f"Event Triggered at: {t[event_start_idx]:.2f}s (RMS={rms[event_start_idx]:.2f})")
    
    # 1. Fixed Lookback (5s)
    fixed_time = t[event_start_idx] - 5.0
    print(f"Fixed Lookback (5s): {fixed_time:.2f}s")
    
    # 2. Smart Lookback
    smart_time = smart_lookback(rms, event_start_idx, sr, hop, max_lookback_s=5.0)
    print(f"Smart Lookback:      {smart_time:.2f}s")
    
    print("-" * 30)
    print("Analysis:")
    print(f"Actual 'Quiet' start was around 8.0s.")
    print(f"Fixed went to 5.0s (too far, unrelated background).")
    print(f"Smart went to {smart_time:.2f}s (should be close to 8.0s or 9.0s).")

