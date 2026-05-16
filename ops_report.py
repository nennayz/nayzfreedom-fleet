from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from dashboard_store import list_all_jobs
from notifier import send_weekly_report


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def build_ops_report(root: Path) -> str:
    actions = _read_jsonl(root / "logs" / "ops_actions.jsonl")
    work_activity = _read_jsonl(root / "logs" / "work_activity.jsonl")
    incidents = _read_jsonl(root / "logs" / "ops_incidents.jsonl")
    jobs = list_all_jobs(root)

    action_counts = Counter(str(item.get("action", "unknown")) for item in actions)
    incident_status = Counter(str(item.get("status", "open")) for item in incidents)
    incident_severity = Counter(str(item.get("severity", "info")) for item in incidents)
    publish_counts: Counter[str] = Counter()
    for job in jobs:
        for platform, value in (job.publish_result or {}).items():
            if isinstance(value, dict):
                publish_counts[f"{platform}:{value.get('status', 'unknown')}"] += 1
    failed_jobs = [
        job for job in jobs
        if getattr(job.status, "value", str(job.status)) == "failed"
    ]

    latest_action = actions[-1].get("action", "none") if actions else "none"
    latest_work = work_activity[-1].get("summary", "none") if work_activity else "none"
    latest_incident = incidents[-1].get("title", "none") if incidents else "none"
    lines = [
        "Slayhack weekly Ops report",
        f"ops_actions_total={len(actions)} latest_action={latest_action}",
        f"work_activity_total={len(work_activity)} latest_work={latest_work}",
        (
            "actions "
            f"smoke_test={action_counts['smoke_test']} "
            f"backup={action_counts['backup']} "
            f"instagram_queue={action_counts['instagram_queue']} "
            f"production_summary={action_counts['production_summary']} "
            f"restart_dashboard={action_counts['restart_dashboard']}"
        ),
        (
            "incidents "
            f"total={len(incidents)} "
            f"open={incident_status['open']} "
            f"investigating={incident_status['investigating']} "
            f"resolved={incident_status['resolved']} "
            f"critical={incident_severity['critical']} "
            f"latest={latest_incident}"
        ),
        f"jobs total={len(jobs)} failed={len(failed_jobs)} latest={jobs[0].id if jobs else 'none'}",
        (
            "publish "
            f"facebook_scheduled={publish_counts['facebook:scheduled']} "
            f"instagram_pending_queue={publish_counts['instagram:pending_queue']} "
            f"instagram_retrying={publish_counts['instagram:retrying']} "
            f"instagram_failed={publish_counts['instagram:failed']}"
        ),
    ]
    if failed_jobs:
        lines.append("recent_failed_jobs=" + ",".join(job.id for job in failed_jobs[:5]))
    return "\n".join(lines)


def write_ops_report_log(root: Path, report: str) -> None:
    path = root / "logs" / "ops_reports.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = report.splitlines()
    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "title": lines[0] if lines else "Slayhack weekly Ops report",
        "line_count": len(lines),
        "report": report,
    }
    with path.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a weekly Slayhack Ops report.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    report = build_ops_report(root)
    send_weekly_report(report.splitlines(), dry_run=args.dry_run)
    if not args.dry_run:
        write_ops_report_log(root, report)


if __name__ == "__main__":
    main()
