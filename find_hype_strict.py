import librosa
import numpy as np
from moviepy import VideoFileClip


def analyze_volumes(video_path):
    print(f"--- 🕵️ SPYING ON: {video_path} ---")
    clip = VideoFileClip(video_path)
    audio_path = "temp_audio.wav"
    clip.audio.write_audiofile(audio_path, logger=None)

    y, sr = librosa.load(audio_path)

    # 1. Aggressive Separation again
    y_harmonic, y_percussive = librosa.effects.hpss(y, margin=(1.0, 5.0))
    rms = librosa.feature.rms(y=y_percussive)[0]
    times = librosa.times_like(rms, sr=sr)

    # 2. Find peaks
    # We set a tiny threshold just to get ALL percussive sounds
    threshold = 0.05
    hype_mask = rms > threshold

    segments = []
    in_segment = False
    start_time = 0
    max_vol_in_segment = 0

    for i, is_hype in enumerate(hype_mask):
        vol = rms[i]
        t = times[i]

        if is_hype and not in_segment:
            in_segment = True
            start_time = t
            max_vol_in_segment = vol

        elif is_hype and in_segment:
            # Keep track of the loudest point in this clip
            if vol > max_vol_in_segment:
                max_vol_in_segment = vol

        elif not is_hype and in_segment:
            in_segment = False
            duration = t - start_time
            if duration > 0.1:
                segments.append((start_time, t, max_vol_in_segment))

    print(f"\n--- 📊 VOLUME REPORT ---")
    print(
        f"Look at the 'Vol' number. We need to pick a number HIGHER than the Grenade line."
    )
    print("-" * 40)

    for start, end, vol in segments:
        # Check if this is our problematic Grenade timestamp (approx 18.4s)
        marker = ""
        if 18.0 <= start <= 19.0:
            marker = " 👈 (THE GRENADE?)"

        print(f"⏰ {start:.2f}s -> {end:.2f}s | Vol: {vol:.4f}{marker}")


if __name__ == "__main__":
    analyze_volumes("my_gameplay.mp4")
