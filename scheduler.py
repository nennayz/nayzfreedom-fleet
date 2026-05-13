from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path
import yaml

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
    from datetime import datetime
    return datetime.now().strftime("%A").lower()


def run_scheduler(dry_run: bool = False, root: Path | None = None) -> int:
    _root = root if root is not None else _ROOT
    calendars = sorted(_root.glob("projects/*/weekly_calendar.yaml"))
    if not calendars:
        logger.warning("No weekly_calendar.yaml found under projects/")
        return 0

    today = _today_name()
    any_failed = False

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
            result = subprocess.run(cmd)
            if result.returncode != 0:
                logger.error("FAILED: project=%s key=%s brief=%r", project_slug, key, brief)
                any_failed = True
            else:
                logger.info("OK: project=%s key=%s", project_slug, key)

    return 1 if any_failed else 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NayzFreedom daily content scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to each main.py call")
    args = parser.parse_args()
    sys.exit(run_scheduler(dry_run=args.dry_run))
