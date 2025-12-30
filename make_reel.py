import librosa
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips

def create_cinematic_reel(video_path, output_name="hype_reel.mp4"):
    
    # --- 1. CONFIGURATION ---
    HARD_THRESHOLD = 0.10   # The volume trigger we found
    MIN_DURATION = 0.1      # Detect even quick pistol taps
    
    # CHANGED: Increased padding to give context (aiming + kill confirm)
    PADDING = 1.0           
    
    # NEW: If two shots are within this many seconds, merge them into one clip
    MERGE_GAP = 2.0         

    print(f"--- 🎬 LOADING VIDEO: {video_path} ---")
    clip = VideoFileClip(video_path)
    
    audio_path = "temp_audio.wav"
    clip.audio.write_audiofile(audio_path, logger=None)
    
    print("--- 🧠 ANALYZING ACTION ---")
    y, sr = librosa.load(audio_path)
    y_harmonic, y_percussive = librosa.effects.hpss(y, margin=(1.0, 5.0))
    rms = librosa.feature.rms(y=y_percussive)[0]
    times = librosa.times_like(rms, sr=sr)
    
    hype_mask = rms > HARD_THRESHOLD
    
    # Step 1: Find raw impact moments
    raw_segments = []
    in_segment = False
    start_time = 0
    
    for i, is_hype in enumerate(hype_mask):
        t = times[i]
        if is_hype and not in_segment:
            in_segment = True
            start_time = t
        elif not is_hype and in_segment:
            in_segment = False
            duration = t - start_time
            if duration >= MIN_DURATION:
                raw_segments.append((start_time, t))

    # Step 2: Add Padding
    padded_segments = []
    for start, end in raw_segments:
        # Start earlier (aiming), end later (follow through)
        p_start = max(0, start - PADDING)
        p_end = min(clip.duration, end + PADDING)
        padded_segments.append((p_start, p_end))

    # Step 3: Merge Overlapping Clips (The "Smoothness" Fix)
    # If Clip A ends at 10s and Clip B starts at 10.5s, combine them!
    final_segments = []
    if padded_segments:
        padded_segments.sort() # Ensure they are in order
        
        # Start with the first clip
        curr_start, curr_end = padded_segments[0]
        
        for next_start, next_end in padded_segments[1:]:
            # If the next clip starts before the current one ends (plus a tiny gap)
            if next_start <= curr_end + 0.5: 
                # Extend the current clip
                curr_end = max(curr_end, next_end)
            else:
                # Close the current clip and start a new one
                final_segments.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        
        # Append the last one
        final_segments.append((curr_start, curr_end))

    print(f"--- ✂️ FOUND {len(final_segments)} SCENES (Merged from {len(raw_segments)} shots) ---")
    
    # --- 4. RENDER ---
    final_clips = []
    for start, end in final_segments:
        print(f"  -> Scene: {start:.2f}s to {end:.2f}s")
        subclip = clip.subclip(start, end)
        final_clips.append(subclip)
    
    if len(final_clips) > 0:
        final_montage = concatenate_videoclips(final_clips)
        final_montage.write_videofile(output_name, codec="libx264", audio_codec="aac")
        print(f"\n✅ DONE! Saved as '{output_name}'")
    else:
        print("❌ No moments found.")

if __name__ == "__main__":
    create_cinematic_reel("my_gameplay.mp4")