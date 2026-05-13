from __future__ import annotations
import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from models.content_job import ContentJob, PostPerformance
from notifier import send_weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent


@dataclass
class PlatformStats:
    job_count: int = 0
    total_reach: int = 0
    total_likes: int = 0
    total_saves: int = 0
    total_shares: int = 0
    top_job_id: str = ""
    top_job_brief: str = ""
    top_job_reach: int = 0


def _in_window(job_id: str, today: date) -> bool:
    try:
        job_date = date(int(job_id[:4]), int(job_id[4:6]), int(job_id[6:8]))
        return (today - timedelta(days=6)) <= job_date <= today
    except (ValueError, IndexError):
        return False


def _latest_perf_per_platform(performances: list[PostPerformance]) -> dict[str, PostPerformance]:
    latest: dict[str, PostPerformance] = {}
    for p in performances:
        if p.platform not in latest:
            latest[p.platform] = p
        else:
            existing = latest[p.platform]
            if p.recorded_at is not None and (
                existing.recorded_at is None or p.recorded_at > existing.recorded_at
            ):
                latest[p.platform] = p
    return latest


def collect_week_data(root: Path, today: date) -> dict[str, dict[str, PlatformStats]]:
    output_dir = root / "output"
    if not output_dir.exists():
        return {}

    result: dict[str, dict[str, PlatformStats]] = {}

    for job_file in output_dir.glob("*/*/job.json"):
        page_name = job_file.parent.parent.name
        try:
            job = ContentJob.model_validate_json(job_file.read_text())
        except Exception as exc:
            logger.warning("Skipping corrupt job file %s: %s", job_file, exc)
            continue

        if not _in_window(job.id, today):
            continue

        if not job.performance:
            continue

        latest = _latest_perf_per_platform(job.performance)

        if page_name not in result:
            result[page_name] = {}

        for platform, perf in latest.items():
            if platform not in result[page_name]:
                result[page_name][platform] = PlatformStats()
            stats = result[page_name][platform]
            stats.job_count += 1
            reach = perf.reach or 0
            stats.total_reach += reach
            stats.total_likes += perf.likes or 0
            stats.total_saves += perf.saves or 0
            stats.total_shares += perf.shares or 0
            if (not stats.top_job_id) or reach > stats.top_job_reach or (
                reach == stats.top_job_reach and job.id < stats.top_job_id
            ):
                stats.top_job_id = job.id
                stats.top_job_brief = job.brief
                stats.top_job_reach = reach

    return result
