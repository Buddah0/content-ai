import argparse
import sys
from . import pipeline
from . import renderer


def main():
    parser = argparse.ArgumentParser(
        prog="content-ai", description="AI Gameplay Highlight Detector"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # SCAN
    scan_parser = subparsers.add_parser(
        "scan", help="Scan files/folders and create montage"
    )
    scan_parser.add_argument(
        "--input", "-i", type=str, help="Input file or folder"
    )
    scan_parser.add_argument(
        "--demo", action="store_true", help="Run demo mode with bundled sample"
    )
    scan_parser.add_argument(
        "--output", "-o", type=str, default="output", help="Output directory"
    )
    scan_parser.add_argument(
        "--recursive", "-r", action="store_true", help="Recursive scan"
    )
    scan_parser.add_argument(
        "--ext", type=str, help="Comma-separated extensions (mp4,mov)"
    )
    scan_parser.add_argument("--limit", type=int, help="Max inputs to process")

    scan_parser.add_argument(
        "--rms-threshold", type=float, help="Override RMS threshold"
    )

    scan_parser.add_argument(
        "--max-duration", type=float, help="Max montage duration (s)"
    )
    scan_parser.add_argument("--max-segments", type=int, help="Max segments in montage")
    scan_parser.add_argument(
        "--order",
        choices=["chronological", "score", "hybrid"],
        help="Ordering strategy",
    )
    scan_parser.add_argument(
        "--keep-temp", action="store_true", help="Keep intermediate clip files"
    )

    # CHECK FFMPEG
    check_parser = subparsers.add_parser("check", help="Verify dependencies")

    args = parser.parse_args()

    if args.command == "scan":
        # Convert args to dict, filtering None
        cli_dict = {k: v for k, v in vars(args).items() if v is not None}
        pipeline.run_scan(cli_dict)

    elif args.command == "check":
        print("Checking dependencies...")
        if renderer.check_ffmpeg():
            print("✅ ffmpeg found.")
        else:
            print("❌ ffmpeg NOT found in PATH.")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
