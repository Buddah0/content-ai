import os
import subprocess
from pathlib import Path
from moviepy.editor import VideoFileClip
from typing import List, Dict, Any
import imageio_ffmpeg


def get_ffmpeg_cmd():
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_segment_to_file(
    source_path: str, start: float, end: float, output_path: str
):
    """
    Render a single segment to a temporary file.
    """
    # Use moviepy to cut and save
    # We use a context manager to ensure the source is closed
    with VideoFileClip(source_path) as video:
        # Clamp timestamps just in case
        start = max(0, start)
        end = min(video.duration, end)

        if end <= start:
            return  # Skip invalid

        new_clip = video.subclipped(start, end)
        # using 'fast' preset for speed, crf for quality
        # audio_codec aac is standard
        new_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=f"temp_render_audio_{os.getpid()}.m4a",
            remove_temp=True,
            logger=None,
            preset="ultrafast",  # optimize for speed as requested "short form"
        )


def build_montage_from_list(segment_files: List[str], output_file: str):
    """
    Concatenate a list of video files using ffmpeg concat demuxer.
    """
    if not segment_files:
        return

    # Create list file
    list_path = f"concat_list_{os.getpid()}.txt"
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for path in segment_files:
                # FFMPEG requires absolute paths or relative. Let's use absolute.
                # Escape backslashes for Windows if needed, but forward slashes usually work.
                # 'file' keyword is required.
                abs_path = Path(path).resolve()
                f.write(f"file '{str(abs_path).replace(os.sep, '/')}'\n")

        # Run ffmpeg
        # ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
        ffmpeg_exe = get_ffmpeg_cmd()
        cmd = [
            ffmpeg_exe,
            "-y",  # overwrite
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            output_file,
        ]

        print(f"Running ffmpeg concat...")
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )

    except subprocess.CalledProcessError as e:
        print(f"FFMPEG Error: {e.stderr.decode() if e.stderr else 'Unknown'}")
        raise e
    except Exception as e:
        print(f"Error building montage: {e}")
        raise e
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)


def check_ffmpeg():
    """Verify ffmpeg is installed."""
    try:
        # Get path and verify it exists/runs
        exe = get_ffmpeg_cmd()
        subprocess.run(
            [exe, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except:
        return False
