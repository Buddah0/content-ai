"""
Demo asset generation for the One-Command Promise.

This module creates a synthetic demo video with percussive audio spikes
for testing and demonstration purposes.
"""

import os
from pathlib import Path

import numpy as np
from moviepy.editor import (
    AudioClip,
    ColorClip,
)


def generate_demo_video(output_path: str, duration: float = 30.0) -> str:
    """
    Generate a synthetic demo video with percussive audio events.

    Creates a simple video with:
    - Colored background
    - Synthetic audio with injected percussive spikes at specific timestamps
    - Timestamps designed to test Smart Merging logic

    Args:
        output_path: Where to save the demo video
        duration: Total duration in seconds

    Returns:
        Path to the generated demo video
    """
    fps = 24
    sample_rate = 44100

    # Event timestamps (in seconds) - designed to test merging
    # Events at: 2s, 4s (gap=2s, should merge with default merge_gap=2.0)
    #            10s, 15s (gap=5s, should NOT merge)
    #            20s, 21s, 22s (gaps=1s, should all merge into one segment)
    event_times = [2.0, 4.0, 10.0, 15.0, 20.0, 21.0, 22.0]

    def make_audio(t):
        """Generate audio with percussive spikes at event_times."""
        # Base noise (very quiet)
        signal = np.random.normal(0, 0.01, len(t))

        # Add percussive spikes
        for event_time in event_times:
            # Find samples near this event
            event_samples = np.abs(t - event_time) < 0.1  # 100ms spike
            # High amplitude spike
            signal[event_samples] = np.random.normal(0, 0.3, np.sum(event_samples))

        # Ensure mono output
        return signal

    # Create video clip (simple colored background)
    video_clip = ColorClip(size=(640, 480), color=(20, 20, 40), duration=duration)
    video_clip = video_clip.set_fps(fps)

    # Create audio clip
    audio_clip = AudioClip(make_audio, duration=duration, fps=sample_rate)

    # Combine
    final_clip = video_clip.set_audio(audio_clip)

    # Write to file
    output_path = str(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"Generating demo video: {output_path}")
    final_clip.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
        preset="ultrafast",
    )

    final_clip.close()

    return output_path


def get_demo_asset_path() -> Path:
    """
    Get or create the demo asset.

    Returns:
        Path to demo video file.
    """
    assets_dir = Path(__file__).parent.parent / "assets" / "demo"
    demo_file = assets_dir / "sample.mp4"

    if not demo_file.exists():
        print("Demo asset not found. Generating synthetic demo video...")
        assets_dir.mkdir(parents=True, exist_ok=True)
        generate_demo_video(str(demo_file), duration=30.0)

    return demo_file
