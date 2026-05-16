from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from dashboard_store import list_all_jobs
from notifier import send_healthcheck_alert


def build_summary(root: Path) -> str:
    jobs = list_all_jobs(root)
    status_counts = Counter(getattr(job.status, "value", str(job.status)) for job in jobs)
    publish_counts: Counter[str] = Counter()

    for job in jobs:
        for platform, value in (job.publish_result or {}).items():
            if isinstance(value, dict):
                publish_counts[f"{platform}:{value.get('status', 'unknown')}"] += 1

    latest = jobs[0].id if jobs else "none"
    lines = [
        "Slayhack production summary",
        f"total_jobs={len(jobs)} latest_job={latest}",
        (
            "status "
            f"completed={status_counts['completed']} "
            f"failed={status_counts['failed']} "
            f"running={status_counts['running']} "
            f"awaiting_approval={status_counts['awaiting_approval']}"
        ),
        (
            "publish "
            f"facebook_scheduled={publish_counts['facebook:scheduled']} "
            f"instagram_published={publish_counts['instagram:published']} "
            f"instagram_pending_queue={publish_counts['instagram:pending_queue']} "
            f"failed={sum(count for key, count in publish_counts.items() if key.endswith(':failed'))}"
        ),
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a daily Slayhack production summary.")
    parser.add_argument("--root", default=".", help="Project root containing output/")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    load_dotenv(root / ".env")
    send_healthcheck_alert(build_summary(root), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
