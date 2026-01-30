import librosa
import numpy as np
from moviepy import VideoFileClip


def find_hype_moments(video_path, hype_threshold=3.0, min_duration=0.5):
    """
    Uses 'Percussive' separation to distinguish gunshots from voice lines.
    """

    print(f"--- 🎮 LOADING: {video_path} ---")
    clip = VideoFileClip(video_path)
    audio_path = "temp_audio.wav"
    clip.audio.write_audiofile(audio_path, logger=None)

    print("--- 🧠 SEPARATING VOICE FROM ACTION ---")
    # Load the audio
    y, sr = librosa.load(audio_path)

    # SPLIT harmonic (voice/music) from percussive (shots/explosions)
    y_harmonic, y_percussive = librosa.effects.hpss(y)

    # Analyze ONLY the percussive part
    rms = librosa.feature.rms(y=y_percussive)[0]
    times = librosa.times_like(rms, sr=sr)

    # Logic
    avg_volume = np.mean(rms)
    hype_limit = avg_volume * hype_threshold

    print(f"Average Percussive Level: {avg_volume:.5f}")
    print(f"Percussion Threshold: {hype_limit:.5f}")

    hype_mask = rms > hype_limit

    segments = []
    in_segment = False
    start_time = 0

    for i, is_hype in enumerate(hype_mask):
        current_time = times[i]
        if is_hype and not in_segment:
            in_segment = True
            start_time = current_time
        elif not is_hype and in_segment:
            in_segment = False
            duration = current_time - start_time
            if duration >= min_duration:
                segments.append((start_time, current_time))

    print("\n--- 🔥 PERCUSSIVE HYPE REPORT ---")
    print(f"Found {len(segments)} action moments:")
    for start, end in segments:
        print(f"⏰ {start:.2f}s -> {end:.2f}s")

    return segments


if __name__ == "__main__":
    try:
        # Note: We can use a higher threshold (3.0) because percussive spikes
        # (gunshots) are usually MUCH sharper than the background noise.
        find_hype_moments("my_gameplay.mp4", hype_threshold=3.0, min_duration=0.5)
    except OSError:
        print("❌ Error: Could not find 'my_gameplay.mp4'.")
