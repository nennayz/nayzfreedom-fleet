from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from agents.publish import PublishAgent
from activity_logger import log_action, log_command
from config import Config, MissingAPIKeyError
from job_store import find_job, save_job
from models.content_job import ContentJob, JobStatus
from orchestrator import Orchestrator
from project_loader import load_project, ProjectNotFoundError
from tracker import track_job

_LOCK_FILE = Path("/tmp/nayz_pipeline.lock")


def main() -> None:
    parser = argparse.ArgumentParser(description="Slay Hack Agency — AI Content Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Project slug (folder name under projects/)")
    group.add_argument("--resume", metavar="JOB_ID", help="Resume an interrupted job by ID")
    group.add_argument("--publish-only", metavar="JOB_ID",
                       help="Publish a completed job by ID (skips content generation)")
    group.add_argument("--track", metavar="JOB_ID",
                       help="Fetch and record post metrics for a published job")
    parser.add_argument("--brief", help="Content brief (required with --project)")
    parser.add_argument("--platforms", default="instagram,facebook",
                        help="Comma-separated platforms (default: instagram,facebook)")
    parser.add_argument("--dry-run", action="store_true", help="Run with mock data, no API calls")
    parser.add_argument("--schedule", action="store_true",
                        help="Schedule post at Roxy's recommended time instead of immediately")
    parser.add_argument(
        "--content-type",
        choices=["video", "article", "image", "infographic"],
        dest="content_type",
        help="Pre-set content type (used by scheduler to skip AI inference)",
    )
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="Auto-approve all checkpoints — required when running from cron",
    )
    args = parser.parse_args()
    log_command("main_invocation", {"argv": sys.argv[1:]})

    try:
        config = Config.from_env()
    except MissingAPIKeyError as e:
        log_action("config_error", {"error": str(e)})
        print(f"Error: {e}\nCopy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    if args.publish_only:
        log_command("publish_only", {"job_id": args.publish_only, "schedule": args.schedule})
        try:
            job = find_job(args.publish_only)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        if job.stage != "emma_done":
            print(f"Error: job {job.id} is at stage '{job.stage}', expected 'emma_done'. "
                  "Run the full pipeline first.")
            sys.exit(1)
        print(f"Publishing job {job.id} for {job.pm.page_name} (schedule={args.schedule})")
        agent = PublishAgent(config)
        result = agent.run(job, schedule=args.schedule)
        save_job(result)
        statuses = {p: v.get("status") for p, v in (result.publish_result or {}).items()}
        print(f"Publish complete: {statuses}")
        return

    if args.track:
        log_command("track", {"job_id": args.track})
        try:
            job = find_job(args.track)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        if job.stage != "publish_done":
            print(f"Error: job {job.id} is at stage '{job.stage}', expected 'publish_done'.")
            sys.exit(1)
        print(f"Tracking job {job.id} for {job.pm.page_name}")
        job = track_job(job, config)
        save_job(job)
        if not job.performance:
            print("No metrics available.")
        else:
            _epoch = datetime.min.replace(tzinfo=timezone.utc)
            latest: dict = {}
            for p in sorted(job.performance, key=lambda x: x.recorded_at or _epoch):
                latest[p.platform] = p
            for platform, p in latest.items():
                print(
                    f"{platform}: likes={p.likes}, reach={p.reach}, "
                    f"shares={p.shares}, saves={p.saves}"
                )
        return

    if args.resume:
        try:
            job = find_job(args.resume)
            log_command("resume_job", {"job_id": args.resume})
            print(f"Resuming job {job.id} for {job.pm.page_name} (stage: {job.stage})")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        if not args.brief:
            print("Error: --brief is required when using --project")
            sys.exit(1)
        try:
            pm = load_project(args.project)
        except ProjectNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        platforms = [p.strip() for p in args.platforms.split(",")]
        job = ContentJob(
            project=args.project,
            pm=pm,
            brief=args.brief,
            platforms=platforms,
            dry_run=args.dry_run,
        )
        if args.content_type:
            from models.content_job import ContentType as CT
            job.content_type = CT(args.content_type)
        save_job(job)
        log_command("start_job", {
            "job_id": job.id,
            "project": args.project,
            "brief": args.brief,
            "platforms": platforms,
            "content_type": args.content_type,
            "dry_run": args.dry_run,
        })
        print(f"Starting job {job.id} for {pm.page_name}")
        if args.dry_run:
            print("[DRY-RUN MODE] No real API calls will be made.\n")

    orchestrator = Orchestrator(config)
    try:
        result = orchestrator.run(job, unattended=args.unattended)
    finally:
        _LOCK_FILE.unlink(missing_ok=True)

    if result.status == JobStatus.COMPLETED:
        out_dir = f"output/{result.pm.page_name}/{result.id}"
        print(f"\nJob complete! Output saved to: {out_dir}")
    else:
        print(f"\nJob ended with status: {result.status}")


if __name__ == "__main__":
    main()
