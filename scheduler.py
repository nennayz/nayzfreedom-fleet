from __future__ import annotations
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import yaml
from activity_logger import log_action, log_command
from notifier import send_slack_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent

_KEY_TO_CONTENT_TYPE: dict[str, str] = {
    "short_video_1": "video",
    "short_video_2": "video",
    "long_video": "video",
    "article_1": "article",
    "article_2": "article",
    "infographic_1": "infographic",
    "infographic_2": "infographic",
}

_BRIEF_KEYS = list(_KEY_TO_CONTENT_TYPE.keys())


def _today_name() -> str:
    return datetime.now().strftime("%A").lower()


def _video_generation_available() -> bool:
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        return False
    credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if credentials:
        return Path(credentials).expanduser().exists()
    return (Path.home() / ".config/gcloud/application_default_credentials.json").exists()


def run_scheduler(dry_run: bool = False, root: Path | None = None) -> int:
    _root = root if root is not None else _ROOT
    calendars = sorted(_root.glob("projects/*/weekly_calendar.yaml"))
    if not calendars:
        logger.warning("No weekly_calendar.yaml found under projects/")
        return 0

    today = _today_name()
    run_date = datetime.now().strftime("%Y-%m-%d")
    failures: list[dict] = []
    total = 0

    log_action("scheduler_start", {"run_date": run_date, "dry_run": dry_run})
    for calendar_path in calendars:
        project_slug = calendar_path.parent.name
        with open(calendar_path) as f:
            calendar: dict = yaml.safe_load(f) or {}

        day_entry: dict = calendar.get(today, {})
        if not day_entry:
            logger.warning("No calendar entry for %s in %s — skipping", today, calendar_path)
            continue

        for key in _BRIEF_KEYS:
            brief = day_entry.get(key, "")
            if not brief:
                logger.warning("Blank brief for key=%s project=%s — skipping", key, project_slug)
                continue

            content_type = _KEY_TO_CONTENT_TYPE[key]
            if root is None and not dry_run and content_type == "video" and not _video_generation_available():
                logger.warning(
                    "Skipping video job because Google video credentials are not configured: "
                    "project=%s key=%s",
                    project_slug,
                    key,
                )
                continue
            total += 1
            cmd = [
                sys.executable, "main.py",
                "--project", project_slug,
                "--brief", brief,
                "--content-type", content_type,
                "--schedule",
                "--unattended",
            ]
            if dry_run:
                cmd.append("--dry-run")

            logger.info("Running: project=%s key=%s content_type=%s", project_slug, key, content_type)
            log_command("scheduler_run_command", {
                "project": project_slug,
                "key": key,
                "content_type": content_type,
                "cmd": cmd,
                "dry_run": dry_run,
            })
            try:
                result = subprocess.run(cmd, cwd=_root, timeout=1800)
            except subprocess.TimeoutExpired as exc:
                if exc.process:
                    exc.process.kill()
                    exc.process.communicate()
                logger.error("TIMEOUT: project=%s key=%s", project_slug, key)
                failures.append({"project": project_slug, "brief": key, "content_type": content_type, "exit_code": None})
                continue
            if result.returncode != 0:
                logger.error("FAILED: project=%s key=%s brief=%r", project_slug, key, brief)
                failures.append({"project": project_slug, "brief": key, "content_type": content_type, "exit_code": result.returncode})
            else:
                logger.info("OK: project=%s key=%s", project_slug, key)

    if failures:
        send_slack_alert(failures, run_date, total, dry_run=dry_run)
    log_action("scheduler_complete", {
        "run_date": run_date,
        "total": total,
        "failures": len(failures),
    })

    return 1 if failures else 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NayzFreedom daily content scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to each main.py call")
    args = parser.parse_args()
    sys.exit(run_scheduler(dry_run=args.dry_run))
