from __future__ import annotations
import argparse
import sys
from agents.publish import PublishAgent
from config import Config, MissingAPIKeyError
from job_store import find_job, save_job
from models.content_job import ContentJob, JobStatus
from orchestrator import Orchestrator
from project_loader import load_project, ProjectNotFoundError


def main() -> None:
    parser = argparse.ArgumentParser(description="Slay Hack Agency — AI Content Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Project slug (folder name under projects/)")
    group.add_argument("--resume", metavar="JOB_ID", help="Resume an interrupted job by ID")
    group.add_argument("--publish-only", metavar="JOB_ID",
                       help="Publish a completed job by ID (skips content generation)")
    parser.add_argument("--brief", help="Content brief (required with --project)")
    parser.add_argument("--platforms", default="instagram,facebook",
                        help="Comma-separated platforms (default: instagram,facebook)")
    parser.add_argument("--dry-run", action="store_true", help="Run with mock data, no API calls")
    parser.add_argument("--schedule", action="store_true",
                        help="Schedule post at Roxy's recommended time instead of immediately")
    args = parser.parse_args()

    try:
        config = Config.from_env()
    except MissingAPIKeyError as e:
        print(f"Error: {e}\nCopy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    if args.publish_only:
        try:
            job = find_job(args.publish_only)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        print(f"Publishing job {job.id} for {job.pm.page_name} (schedule={args.schedule})")
        agent = PublishAgent(config)
        result = agent.run(job, schedule=args.schedule)
        save_job(result)
        print(f"Publish complete: {result.publish_result}")
        return

    if args.resume:
        try:
            job = find_job(args.resume)
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
        save_job(job)
        print(f"Starting job {job.id} for {pm.page_name}")
        if args.dry_run:
            print("[DRY-RUN MODE] No real API calls will be made.\n")

    orchestrator = Orchestrator(config)
    result = orchestrator.run(job)

    if result.status == JobStatus.COMPLETED:
        out_dir = f"output/{result.pm.page_name}/{result.id}"
        print(f"\nJob complete! Output saved to: {out_dir}")
    else:
        print(f"\nJob ended with status: {result.status}")


if __name__ == "__main__":
    main()
