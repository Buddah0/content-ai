import argparse
import sys

from . import pipeline, queued_pipeline, renderer


def main():
    parser = argparse.ArgumentParser(
        prog="content-ai", description="AI Gameplay Highlight Detector"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # SCAN
    scan_parser = subparsers.add_parser("scan", help="Scan files/folders and create montage")
    scan_parser.add_argument("--input", "-i", type=str, help="Input file or folder")
    scan_parser.add_argument(
        "--demo", action="store_true", help="Run demo mode with bundled sample"
    )
    scan_parser.add_argument("--output", "-o", type=str, default="output", help="Output directory")
    scan_parser.add_argument("--recursive", "-r", action="store_true", help="Recursive scan")
    scan_parser.add_argument("--ext", type=str, help="Comma-separated extensions (mp4,mov)")
    scan_parser.add_argument("--limit", type=int, help="Max inputs to process")

    scan_parser.add_argument("--rms-threshold", type=float, help="Override RMS threshold")

    scan_parser.add_argument("--max-duration", type=float, help="Max montage duration (s)")
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
    subparsers.add_parser("check", help="Verify dependencies")

    # PROCESS (Queue-based batch processing)
    process_parser = subparsers.add_parser(
        "process", help="Queue-based batch processing (resumable)"
    )
    process_parser.add_argument("--input", "-i", type=str, help="Input file or folder")
    process_parser.add_argument(
        "--output", "-o", type=str, default="output", help="Output directory"
    )
    process_parser.add_argument("--recursive", "-r", action="store_true", help="Recursive scan")
    process_parser.add_argument("--ext", type=str, help="Comma-separated extensions (mp4,mov)")
    process_parser.add_argument("--limit", type=int, help="Max inputs to process")
    process_parser.add_argument("--db", type=str, default="queue.db", help="Queue database path")
    process_parser.add_argument("--workers", "-w", type=int, help="Number of parallel workers")
    process_parser.add_argument(
        "--force", "-f", action="store_true", help="Reprocess all (ignore cache)"
    )
    process_parser.add_argument(
        "--no-process", action="store_true", help="Enqueue only, don't process"
    )
    process_parser.add_argument("--rms-threshold", type=float, help="Override RMS threshold")
    process_parser.add_argument("--max-duration", type=float, help="Max montage duration (s)")
    process_parser.add_argument("--max-segments", type=int, help="Max segments in montage")
    process_parser.add_argument(
        "--order",
        choices=["chronological", "score", "hybrid"],
        help="Ordering strategy",
    )

    # QUEUE subcommands (status, retry, clear)
    queue_parser = subparsers.add_parser("queue", help="Manage job queue")
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command", help="Queue commands")

    # queue status
    status_parser = queue_subparsers.add_parser("status", help="Show queue status")
    status_parser.add_argument("--db", type=str, default="queue.db", help="Queue database path")

    # queue process (process existing queue)
    queue_process_parser = queue_subparsers.add_parser("process", help="Process existing queue")
    queue_process_parser.add_argument(
        "--db", type=str, default="queue.db", help="Queue database path"
    )
    queue_process_parser.add_argument(
        "--workers", "-w", type=int, help="Number of parallel workers"
    )
    queue_process_parser.add_argument(
        "--max-jobs", type=int, help="Maximum number of jobs to process"
    )

    # queue retry
    retry_parser = queue_subparsers.add_parser("retry", help="Retry failed jobs")
    retry_parser.add_argument("--db", type=str, default="queue.db", help="Queue database path")

    # queue clear
    clear_parser = queue_subparsers.add_parser("clear", help="Clear queue")
    clear_parser.add_argument("--db", type=str, default="queue.db", help="Queue database path")
    clear_parser.add_argument("--manifest", action="store_true", help="Also clear manifest cache")

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

    elif args.command == "process":
        # Queue-based batch processing
        cli_dict = {k: v for k, v in vars(args).items() if v is not None}
        queued_pipeline.run_queued_scan(cli_dict)

    elif args.command == "queue":
        # Queue management subcommands
        if args.queue_command == "status":
            stats = queued_pipeline.get_queue_stats(db_path=args.db)
            print("\n" + "=" * 60)
            print("QUEUE STATUS")
            print("=" * 60)
            print(f"Pending:              {stats['pending']}")
            print(f"In Progress:          {stats['in_progress']}")
            print(f"Succeeded:            {stats['succeeded']}")
            print(f"Failed:               {stats['failed']}")
            print(f"Total:                {stats['total']}")
            print("=" * 60)

        elif args.queue_command == "process":
            max_jobs = getattr(args, "max_jobs", None)
            process_stats = queued_pipeline.process_queue(
                db_path=args.db, n_workers=getattr(args, "workers", None), max_jobs=max_jobs
            )
            print("\n" + "=" * 60)
            print("PROCESSING SUMMARY")
            print("=" * 60)
            print(f"Succeeded:            {process_stats['succeeded']}")
            print(f"Failed:               {process_stats['failed']}")
            print(f"Skipped (no clips):   {process_stats['skipped']}")
            print(f"Total duration:       {process_stats['total_duration']:.2f}s")
            print("=" * 60)

        elif args.queue_command == "retry":
            queued_pipeline.retry_failed(db_path=args.db)

        elif args.queue_command == "clear":
            clear_manifest = getattr(args, "manifest", False)
            queued_pipeline.clear_queue(db_path=args.db, clear_manifest=clear_manifest)

        else:
            queue_parser.print_help()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
