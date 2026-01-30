
import os
import subprocess
import json
from typing import List, Dict, Any
from pathlib import Path

# Reuse existing modules
from content_ai.detector import detect_hype
from content_ai.segments import pad_segments, clamp_segments, merge_segments, filter_min_duration
from content_ai.renderer import render_segment_to_file, build_montage_from_list, get_ffmpeg_cmd

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

def render_16_9(source_path: str, output_path: str, user_config: Dict):
    """
    Apply Watermark + Captions to 16:9 source.
    """
    # Build filtergraph
    filters = []
    
    # Watermark
    # 18% width, padding 32px
    if os.path.exists(WATERMARK_PATH):
        # We need to load watermark as input 1
        pass
    
    cmd = [get_ffmpeg_cmd(), "-y", "-i", source_path]
    
    filter_complex = ""
    inputs = 1
    
    # Add Watermark Input
    if os.path.exists(WATERMARK_PATH):
        cmd.extend(["-i", WATERMARK_PATH])
        # Scale watermark to 18% of video width
        # Overlay top-left with padding 32
        # We can assume 1920x1080 for now or use scale2ref
        # [1:v][0:v]scale2ref=w=iw*0.18:h=ow/mdar[wm][vid];[wm]setsar=1[wm_scaled] ...
        # Simpler: just use overlay
        
        # [1:v]scale=iw*0.18:-1[wm];[0:v][wm]overlay=32:32
        filter_complex += f"[1:v]scale=1920*0.18:-1[wm];[0:v][wm]overlay=32:32"
        inputs += 1
    else:
        filter_complex += "[0:v]null" # No-op if missing

    # Add Subtitles (Burn-in)
    # filter_complex += ",subtitles=captions.ass"
    # Note: creating temp ass file in the main flow
    
    if os.path.exists("captions.ass"):
        # If filter_complex was just null, replace it
        if filter_complex == "[0:v]null":
             filter_complex = f"subtitles=captions.ass"
        else:
             filter_complex += f",subtitles=captions.ass"

    cmd.extend(["-filter_complex", filter_complex, "-c:v", "libx264", "-c:a", "copy", output_path])
    
    print(f"Rendering 16:9: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def render_9_16(source_path: str, output_path: str, user_config: Dict):
    """
    Apply Blur BG + Center Crop/Scale + Watermark + Captions.
    Output 1080x1920.
    """
    
    cmd = [get_ffmpeg_cmd(), "-y", "-i", source_path]
    
    # Filter graph construction
    # [0:v]split=2[fg][bg];
    # [bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg2];
    # [fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2];
    # [bg2][fg2]overlay=(W-w)/2:(H-h)/2[base];
    
    # Then watermark on [base]
    # Then subtitles on [base]
    
    filter_parts = [
        "[0:v]split=2[fg][bg]",
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg2]",
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2]",
        "[bg2][fg2]overlay=(W-w)/2:(H-h)/2[base]"
    ]
    
    current_stream = "[base]"
    
    if os.path.exists(WATERMARK_PATH):
        cmd.extend(["-i", WATERMARK_PATH])
        # Watermark on 9:16
        # Start from [base] and [1:v]
        # Scale watermark relative to 1080 width (18% = ~194px)
        # [1:v]scale=1080*0.18:-1[wm];[base][wm]overlay=32:32[base_wm]
        filter_parts.append(f"[1:v]scale=1080*0.18:-1[wm]")
        filter_parts.append(f"{current_stream}[wm]overlay=32:32[wm_out]")
        current_stream = "[wm_out]"
        
    if os.path.exists("captions.ass"):
        filter_parts.append(f"{current_stream}subtitles=captions.ass[final]")
        current_stream = "[final]"
        
    # If last stream name is internal, map it
    # If no effects added after base, map base
    
    filter_complex = ";".join(filter_parts)
    
    # Map the final stream
    # Wait, if we ended with [final] or [wm_out], we need to map it
    # But cmd line needs explicit mapping if we name it
    if not filter_complex.endswith("]"):
        # Implicit output from last filter? No, standard is to map.
        # Let's simple format:
        # We need to map the LAST defined label to output
        pass

    # Better approach: chain safely
    cmd.extend(["-filter_complex", filter_complex, "-map", current_stream, "-c:v", "libx264", "-c:a", "copy", output_path])

    print(f"Rendering 9:16: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_mission_control_pipeline(video_path: str, job_id: str, output_dir: str, user_config: Dict = None):
    """
    Main entry point for the job.
    1. Detect
    2. Segments -> Concat
    3. Generate Outputs
    """
    if user_config is None:
        user_config = {}

    # 1. Detect
    # Merge user_config with internal defaults
    rms_threshold = user_config.get("rmsThreshold", 0.1)
    min_event_duration = user_config.get("minEventDuration", 0.5)
    context_padding = user_config.get("contextPadding", 0.5)
    merge_gap = user_config.get("mergeGap", 1.0)
    max_segment_duration = user_config.get("maxSegmentDuration", 10.0)

    config = {
        "detection": {"rms_threshold": rms_threshold, "min_event_duration_s": min_event_duration},
        "processing": {"min_event_duration_s": min_event_duration}
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
    ass_path = os.path.join(output_dir, "captions.ass") # Use output_dir to avoid conflicts
    generate_ass_captions(segments, ass_path)
    
    # 3. Outputs
    out_16_9 = os.path.join(output_dir, "output_16_9.mp4")
    render_16_9(concat_path, out_16_9, user_config)
    
    out_9_16 = os.path.join(output_dir, "output_9_16.mp4")
    render_9_16(concat_path, out_9_16, user_config)
    
    return [out_16_9, out_9_16], segments

if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        run_mission_control_pipeline(sys.argv[1], "test_job", ".")

