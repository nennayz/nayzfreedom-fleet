from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from agents.publish import PublishAgent, has_publish_failures
from config import Config
from job_store import save_job
from models.content_job import ContentJob, JobStatus


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _pending_instagram_jobs(root: Path, now_ts: int) -> list[ContentJob]:
    jobs: list[ContentJob] = []
    output_dir = root / "output"
    for job_file in output_dir.glob("*/*/job.json"):
        try:
            job = ContentJob.model_validate_json(job_file.read_text())
        except (json.JSONDecodeError, ValueError, OSError):
            continue
        ig_result = (job.publish_result or {}).get("instagram", {})
        if not isinstance(ig_result, dict):
            continue
        if ig_result.get("status") != "pending_queue":
            continue
        due = int(ig_result.get("scheduled_publish_time") or 0)
        if due <= now_ts:
            jobs.append(job)
    return sorted(jobs, key=lambda job: job.id)


def process_instagram_queue(root: Path | None = None, dry_run: bool = False) -> int:
    root = root or Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    config = Config.from_env()
    agent = PublishAgent(config)
    processed = 0
    failures = 0

    for job in _pending_instagram_jobs(root, _now_ts()):
        processed += 1
        if dry_run:
            print(f"would_publish_instagram={job.id}")
            continue

        original_platforms = list(job.platforms)
        original_result = dict(job.publish_result or {})
        job.platforms = ["instagram"]
        job = agent.run(job, schedule=False)
        ig_result = (job.publish_result or {}).get("instagram")
        merged_result = {**original_result, "instagram": ig_result}
        job.publish_result = merged_result
        job.platforms = original_platforms
        if has_publish_failures(merged_result):
            failures += 1
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.COMPLETED
        save_job(job)
        print(f"published_instagram={job.id}:{ig_result.get('status') if isinstance(ig_result, dict) else 'unknown'}")

    print(f"processed={processed} failures={failures}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish queued Instagram jobs when due.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(process_instagram_queue(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
