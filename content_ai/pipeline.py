import os
import time
import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

from . import config as config_lib
from . import scanner
from . import detector
from . import segments as seg_lib
from . import renderer
from . import demo as demo_lib


def get_run_dir(output_base: str) -> Path:
    """Find next run_### directory."""
    base = Path(output_base)
    base.mkdir(parents=True, exist_ok=True)

    i = 1
    while True:
        run_dir = base / f"run_{i:03d}"
        if not run_dir.exists():
            run_dir.mkdir()
            return run_dir
        i += 1


def run_scan(cli_args: Dict[str, Any]):
    """
    Main entry point for 'scan' command.
    """
    # 1. Config
    conf = config_lib.resolve_config(cli_args)

    # Handle demo mode
    is_demo = cli_args.get("demo", False)
    if is_demo:
        print("--- 🎬 DEMO MODE ---")
        demo_asset = demo_lib.get_demo_asset_path()
        cli_args["input"] = str(demo_asset)
        # Force specific output for demo
        cli_args["output"] = "."
        print(f"Using demo asset: {demo_asset}")

    # 2. Output Setup
    output_base = cli_args.get("output", "output")

    # For demo mode, output directly to demo_output.mp4
    if is_demo:
        demo_output_path = Path("demo_output.mp4")
        print(f"Demo output will be saved to: {demo_output_path.absolute()}")
    else:
        demo_output_path = None

    run_dir = get_run_dir(output_base) if not is_demo else Path("output") / "demo_run"
    if is_demo:
        run_dir.mkdir(parents=True, exist_ok=True)

    print(f"--- 🚀 Starting Run in {run_dir} ---")

    # 3. Scan
    input_path = cli_args.get("input")
    if not input_path:
        input_path = "."
    recursive = cli_args.get("recursive", False)
    limit = cli_args.get("limit", None)
    exts = cli_args.get("ext", None)
    if exts and isinstance(exts, str):
        exts = [e.strip() for e in exts.split(",")]

    print(f"Scanning {input_path}...")
    video_files = scanner.scan_input(
        input_path, recursive=recursive, limit=limit, extensions=exts
    )
    print(f"Found {len(video_files)} videos.")

    if not video_files:
        print("No videos found. Exiting.")
        return

    # 4. Process Each File
    all_segments = []

    # Params
    pad_s = conf["processing"]["context_padding_s"]
    merge_s = conf["processing"]["merge_gap_s"]
    max_seg_dur = conf["processing"].get("max_segment_duration_s", None)
    min_dur = conf["detection"]["min_event_duration_s"]

    for v_path in video_files:
        print(f"Processing {v_path.name}...")
        try:
            # Detect
            raw = detector.detect_hype(str(v_path), conf)
            if not raw:
                continue

            # Post-Process (Per File)
            # 1. Pad
            padded = seg_lib.pad_segments(raw, pad_s)
            # 2. Clamp (to video duration, effectively)
            # We captured video_duration in raw segments.
            # But pad_segments returns copies. We need to clamp based on the video duration.
            # Assuming all raw segments from one file have same duration metadata.
            curr_dur = raw[0]["video_duration"]
            clamped = seg_lib.clamp_segments(padded, 0.0, curr_dur)

            # 3. Merge with max duration enforcement
            merged = seg_lib.merge_segments(clamped, merge_s, max_seg_dur)

            # 4. Filter Min Duration (This is usually applied on RAW events in make_reel,
            # but applying it after merge ensures meaningful clips.
            # Original make_reel: Filter raw -> Pad -> Merge.
            # My detector filters raw.
            # So here I just need to ensure I don't result in tiny clips if clamp caused issues?
            # Generally safe to skip, or re-filter.

            # Add metadata
            for s in merged:
                s["source_path"] = str(v_path)
                s["id"] = str(uuid.uuid4())

            all_segments.extend(merged)
            print(f"  -> Found {len(merged)} segments.")

        except Exception as e:
            print(f"Error processing {v_path}: {e}")
            continue

    # 5. Global Ranking / Sorting
    order = conf["output"]["order"]
    max_segs = conf["output"]["max_segments"]
    max_dur = conf["output"]["max_duration_s"]

    print(f"Ordering by {order}...")

    if order == "chronological":
        # Default sort (path, start)
        all_segments.sort(key=lambda x: (x["source_path"], x["start"]))

    elif order == "score":
        # Sort by score desc
        all_segments.sort(
            key=lambda x: (-x.get("score", 0), x["source_path"], x["start"])
        )

    elif order == "hybrid":
        # Group by source
        by_source = {}
        for s in all_segments:
            by_source.setdefault(s["source_path"], []).append(s)

        # Sort each file (by score or start? "sort by (-score, start)" is good for finding best parts of each file)
        for k in by_source:
            by_source[k].sort(key=lambda x: (-x.get("score", 0), x["start"]))

        # Assign ranks
        ranked_list = []
        for k in by_source:
            for i, seg in enumerate(by_source[k]):
                seg["_rank"] = i
                ranked_list.append(seg)

        # Global sort: rank asc, source asc, start asc
        ranked_list.sort(key=lambda x: (x["_rank"], x["source_path"], x["start"]))
        all_segments = ranked_list

    # 6. Apply Limits
    final_segments = []
    total_dur = 0.0

    count = 0
    for seg in all_segments:
        if max_segs and count >= max_segs:
            break

        dur = seg["end"] - seg["start"]
        if max_dur and (total_dur + dur) > max_dur:
            continue  # Try next? Or stop? "Knapsack" is hard. Greedy approach: Stop if overflow?
            # Or skip large ones? Let's just Stop to keep it simple and shorter.
            # Actually, skipping might allow smaller clips to fit.
            # Let's simple break for now to ensure we respect order priority.
            break

        final_segments.append(seg)
        total_dur += dur
        count += 1

    print(f"Selected {len(final_segments)} segments (Total {total_dur:.2f}s).")

    # 7. Render
    montage_path = demo_output_path if is_demo else (run_dir / "montage.mp4")
    if final_segments:
        temp_paths = []
        try:
            print("Rendering clips...")
            for i, seg in enumerate(final_segments):
                out_name = run_dir / f"clip_{i:03d}.mp4"
                renderer.render_segment_to_file(
                    seg["source_path"], seg["start"], seg["end"], str(out_name)
                )
                temp_paths.append(str(out_name))

            print("Building montage...")
            try:
                renderer.build_montage_from_list(temp_paths, str(montage_path))
                print(f"Montage saved to {montage_path}")
            except Exception as e:
                print(f"Failed to build montage: {e}")
                # Don't re-raise, proceeding to save JSONs

        finally:
            if not conf["output"]["keep_temp"]:
                print("Cleaning up temp clips...")
                for p in temp_paths:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except:
                            pass
    else:
        print("No segments selected. Skipping montage.")

    # 8. Save Metadata
    # Segments
    with open(run_dir / "segments.json", "w") as f:
        json.dump(final_segments, f, indent=2)

    # Meta (Diff) & Resolved
    # Resolved
    with open(run_dir / "resolved_config.json", "w") as f:
        json.dump(conf, f, indent=2)

    # Run Meta
    meta = {
        "timestamp": datetime.datetime.now().isoformat(),
        "success": True,
        "input_count": len(video_files),
        "found_segments_total": len(all_segments),
        "selected_segments": len(final_segments),
        "overrides": cli_args,  # Just dumping CLI args as overrides for now + any others
    }
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # 9. Print Run Summary (especially for demo mode)
    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"Files scanned:        {len(video_files)}")
    print(f"Events detected:      {len(all_segments)}")
    print(f"Segments selected:    {len(final_segments)}")
    print(f"Total duration:       {total_dur:.2f}s")
    if final_segments:
        print(f"Output path:          {montage_path.absolute()}")
    print("=" * 60)

    if is_demo:
        print("\n✅ Demo complete! Check demo_output.mp4")
        if final_segments:
            return 0  # Exit code 0 for success
        else:
            print("⚠️ Warning: No segments were detected in demo.")
            return 1

    print("Run Complete.")
    return run_dir
