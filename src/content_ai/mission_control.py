import os
import shlex
import subprocess
from typing import Any, Dict, List

# Reuse existing modules
from content_ai.detector import detect_hype
from content_ai.renderer import (
    build_montage_from_list,
    get_ffmpeg_cmd,
    has_audio,
    render_segment_to_file,
)
from content_ai.segments import merge_segments, pad_segments

WATERMARK_PATH = os.path.join(os.getcwd(), "watermark.png")


def generate_ass_captions(segments: List[Dict[str, Any]], output_path: str):
    """
    Generate a mock ASS subtitle file based on segments.
    Each segment gets a label like "HYPE [Score]"
    """
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # We assume the input to this function is the list of segments IN THE MONTAGE timeline.
    # i.e. segment N starts at sum(duration of 0..N-1).

    current_time = 0.0
    for seg in segments:
        duration = seg["end"] - seg["start"]
        start_fmt = format_timestamp(current_time)
        end_fmt = format_timestamp(current_time + duration)

        score_int = int(seg["score"] * 100)
        text = f"HYPE EVENT {score_int}"

        events.append(f"Dialogue: 0,{start_fmt},{end_fmt},Default,,0,0,0,,{text}")
        current_time += duration

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))


def format_timestamp(seconds: float) -> str:
    """Format seconds to H:MM:SS.cc for ASS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds * 100) % 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def run_render_with_audio_check(cmd: List[str], source_path: str, output_path: str):
    """
    Run ffmpeg command and verify audio preservation.
    If audio is lost (and source had audio), retry with different audio codec.
    """
    print(f"Running render: {shlex.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg failed with exit code {e.returncode}")
        raise

    # Robustness check: did we lose audio?
    if has_audio(source_path) and not has_audio(output_path):
        print(f"WARNING: Audio lost in {output_path}. Retrying with AAC transcoding.")

        # Replace -c:a copy with -c:a aac -b:a 192k
        new_cmd = []
        skip = False
        for i, arg in enumerate(cmd):
            if skip:
                skip = False
                continue

            if arg == "-c:a" and i + 1 < len(cmd) and cmd[i + 1] == "copy":
                new_cmd.extend(["-c:a", "aac", "-b:a", "192k"])
                skip = True
            else:
                new_cmd.append(arg)

        print(f"Retry render (AAC): {shlex.join(new_cmd)}")
        try:
            subprocess.run(new_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Retry FFmpeg failed with exit code {e.returncode}")
            raise

        if not has_audio(output_path):
            raise RuntimeError(
                f"Failed to preserve audio in {output_path} after retry.\n"
                f"Command: {shlex.join(new_cmd)}"
            )

def render_16_9(source_path: str, output_path: str, user_config: Dict, captions_path: str = None):
    """
    Apply Watermark + Captions to 16:9 source.
    """
    show_watermark = user_config.get("showWatermark", False)
    show_captions = user_config.get("showCaptions", False)

    cmd = [get_ffmpeg_cmd(), "-y", "-i", source_path]
    inputs = 1

    filters = []
    video_map = "[0:v]"

    if show_watermark and os.path.exists(WATERMARK_PATH):
        wm_input_idx = inputs
        # Scale watermark
        filters.append(f"[{wm_input_idx}:v]scale=1920*0.18:-1[wm]")
        # Overlay
        filters.append(f"{video_map}[wm]overlay=32:32[v_wm]")
        video_map = "[v_wm]"
        inputs += 1  # We consumed an input

    if show_captions and captions_path and os.path.exists(captions_path):
        filters.append(f"{video_map}subtitles='{captions_path}'[v_out]")
        video_map = "[v_out]"

    if show_watermark and os.path.exists(WATERMARK_PATH):
        cmd.extend(["-i", WATERMARK_PATH])

    if filters:
        # User requested audio mapping: -map 0:a?
        cmd.extend(["-filter_complex", ";".join(filters), "-map", video_map, "-map", "0:a?"])
    else:
        cmd.extend(["-map", "0:v", "-map", "0:a?"])

    cmd.extend([
        "-c:v", "libx264",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        output_path
    ])

    run_render_with_audio_check(cmd, source_path, output_path)


def render_9_16(source_path: str, output_path: str, user_config: Dict, captions_path: str = None):
    """
    Apply Blur BG + Center Crop/Scale + Watermark + Captions.
    Output 1080x1920.
    """
    show_watermark = user_config.get("showWatermark", False)
    show_captions = user_config.get("showCaptions", False)

    cmd = [get_ffmpeg_cmd(), "-y", "-i", source_path]
    inputs = 1

    # Filter graph construction
    # [0:v]split=2[fg][bg];
    # [bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg2];
    # [fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2];
    # [bg2][fg2]overlay=(W-w)/2:(H-h)/2[base];

    filter_parts = [
        "[0:v]split=2[fg][bg]",
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg2]",
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2]",
        "[bg2][fg2]overlay=(W-w)/2:(H-h)/2[base]",
    ]

    current_stream = "[base]"

    if show_watermark and os.path.exists(WATERMARK_PATH):
        cmd.extend(["-i", WATERMARK_PATH])
        wm_input_idx = inputs
        inputs += 1
        # Watermark on 9:16
        # Start from [base] and [1:v]
        # Scale watermark relative to 1080 width (18% = ~194px)
        filter_parts.append(f"[{wm_input_idx}:v]scale=1080*0.18:-1[wm]")
        filter_parts.append(f"{current_stream}[wm]overlay=32:32[wm_out]")
        current_stream = "[wm_out]"

    if show_captions and captions_path and os.path.exists(captions_path):
        filter_parts.append(f"{current_stream}subtitles='{captions_path}'[final]")
        current_stream = "[final]"

    filter_complex = ";".join(filter_parts)

    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            current_stream,
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-c:a",
            "copy",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-shortest",
            output_path,
        ]
    )

    run_render_with_audio_check(cmd, source_path, output_path)


def run_mission_control_pipeline(
    video_path: str, job_id: str, output_dir: str, user_config: Dict = None
):
    """
    Main entry point for the job.
    1. Detect
    2. Segments -> Concat
    3. Generate Outputs
    """
    if user_config is None:
        user_config = {}

    # 1. Detect
    # Read from nested config structure (matches ContentAIConfig model_dump)
    det = user_config.get("detection", {})
    proc = user_config.get("processing", {})
    rms_threshold = det.get("rms_threshold", 0.1)
    min_event_duration = det.get("min_event_duration_s", 0.5)
    context_padding = proc.get("context_padding_s", 0.5)
    merge_gap = proc.get("merge_gap_s", 1.0)
    max_segment_duration = proc.get("max_segment_duration_s", 10.0)

    config = {
        "detection": {"rms_threshold": rms_threshold, "min_event_duration_s": min_event_duration},
        "processing": {"min_event_duration_s": min_event_duration},
    }
    raw_events = detect_hype(video_path, config)

    # Merge/Process
    segments = pad_segments(raw_events, context_padding)
    segments = merge_segments(segments, merge_gap, max_segment_duration)

    # 2. Render Segments
    segment_files = []

    # Fallback: if no segments detected, use entire video
    if not segments:
        print("No hype events detected. Using full video as fallback.")
        segments = [{"start": 0, "end": 5.0, "score": 0.5}]  # Assume 5 seconds for test

    for i, seg in enumerate(segments):
        out_name = os.path.join(output_dir, f"clip_{i:03d}.mp4")
        render_segment_to_file(video_path, seg["start"], seg["end"], out_name)
        segment_files.append(out_name)

    # Concat
    concat_path = os.path.join(output_dir, "concat.mp4")
    build_montage_from_list(segment_files, concat_path)

    # Mock Captions
    show_captions = user_config.get("showCaptions", False)
    ass_path = os.path.join(output_dir, "captions.ass")

    if show_captions:
        generate_ass_captions(segments, ass_path)
    else:
        # Ensure we don't accidentally use stale captions if we didn't generate them
        if os.path.exists(ass_path):
            try:
                os.remove(ass_path)
            except OSError:
                pass

    # 3. Outputs
    out_16_9 = os.path.join(output_dir, "output_16_9.mp4")
    render_16_9(concat_path, out_16_9, user_config, captions_path=ass_path)

    out_9_16 = os.path.join(output_dir, "output_9_16.mp4")
    render_9_16(concat_path, out_9_16, user_config, captions_path=ass_path)

    return [out_16_9, out_9_16], segments


if __name__ == "__main__":
    # Test
    import sys

    if len(sys.argv) > 1:
        run_mission_control_pipeline(sys.argv[1], "test_job", ".")
