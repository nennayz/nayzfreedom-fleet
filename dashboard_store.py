from __future__ import annotations
import logging
from datetime import date
from pathlib import Path

from models.content_job import ContentJob
from reporter import PlatformStats, collect_week_data

logger = logging.getLogger(__name__)


def list_all_jobs(root: Path) -> list[ContentJob]:
    output_dir = root / "output"
    if not output_dir.exists():
        return []
    jobs: list[ContentJob] = []
    for job_file in output_dir.glob("*/*/job.json"):
        try:
            jobs.append(ContentJob.model_validate_json(job_file.read_text()))
        except Exception as exc:
            logger.warning("Skipping corrupt job file %s: %s", job_file, exc)
    return sorted(jobs, key=lambda j: j.id, reverse=True)


def load_performance_all(root: Path) -> dict[str, dict[str, PlatformStats]]:
    return collect_week_data(root, date.today())


def summarize_jobs(jobs: list[ContentJob]) -> dict[str, int]:
    return {
        "total": len(jobs),
        "completed": sum(job.status == "completed" for job in jobs),
        "running": sum(job.status == "running" for job in jobs),
        "failed": sum(job.status == "failed" for job in jobs),
        "awaiting_approval": sum(job.status == "awaiting_approval" for job in jobs),
    }
