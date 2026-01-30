import os
import shutil
import sys

# Add CWD to path if needed (though python does this by default)
sys.path.insert(0, os.getcwd())

from content_ai.pipeline import run_scan


def create_cinematic_reel(video_path, output_name="hype_reel.mp4"):
    print(f"--- 🔄 wrapper: Calling content-ai scan for {video_path} ---")

    # Run scan
    # Limit max duration? Default is 90s.
    # Original make_reel had no max duration loop limit, but it merged everything.
    # To mimic it closely, maybe set max duration high?
    # But for "Shorts/TikTok" default, 90s is reasonable.
    # I'll stick to defaults unless user complains, as this is an "upgrade".

    run_dir = run_scan(
        {
            "input": video_path,
            "limit": 1,
            "output": "output",
            # 'max_duration': 300, # optional extension
        }
    )

    if run_dir:
        montage = run_dir / "montage.mp4"
        if montage.exists():
            shutil.copy(montage, output_name)
            print(f"\n✅ DONE! Copied result to '{output_name}'")
        else:
            print("❌ No montage generated.")
    else:
        print("❌ Scan failed.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        create_cinematic_reel(sys.argv[1])
    else:
        create_cinematic_reel("my_gameplay.mp4")
