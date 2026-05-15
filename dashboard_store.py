from __future__ import annotations
import logging
from datetime import date
from pathlib import Path

from models.content_job import ContentJob
from project_loader import normalize_job_identity
from reporter import PlatformStats, collect_week_data

logger = logging.getLogger(__name__)


def list_all_jobs(root: Path) -> list[ContentJob]:
    output_dir = root / "output"
    if not output_dir.exists():
        return []
    jobs: list[ContentJob] = []
    for job_file in output_dir.glob("*/*/job.json"):
        try:
            job = ContentJob.model_validate_json(job_file.read_text())
            jobs.append(normalize_job_identity(job, root=root))
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


def command_brief(jobs: list[ContentJob]) -> dict[str, str]:
    summary = summarize_jobs(jobs)
    if summary["failed"]:
        return {
            "state": "Needs Captain",
            "action": "Review failed missions before launching new work.",
            "detail": f"{summary['failed']} mission{'s' if summary['failed'] != 1 else ''} failed.",
        }
    if summary["awaiting_approval"]:
        return {
            "state": "Needs Captain",
            "action": "Approve or redirect waiting missions.",
            "detail": f"{summary['awaiting_approval']} mission{'s' if summary['awaiting_approval'] != 1 else ''} awaiting approval.",
        }
    if summary["running"]:
        return {
            "state": "In Motion",
            "action": "Monitor active missions; no blockers are flagged.",
            "detail": f"{summary['running']} mission{'s' if summary['running'] != 1 else ''} currently running.",
        }
    if summary["total"]:
        return {
            "state": "Clear",
            "action": "Launch the next Aurora mission when the brief is ready.",
            "detail": "No active blockers or running missions.",
        }
    return {
        "state": "Ready",
        "action": "Launch the first Aurora mission when the brief is ready.",
        "detail": "No missions have been logged yet.",
    }


def attention_jobs(jobs: list[ContentJob], limit: int = 5) -> list[ContentJob]:
    priority = {"failed": 0, "awaiting_approval": 1}
    items = [
        job for job in jobs
        if getattr(job.status, "value", str(job.status)) in priority
    ]
    return sorted(
        items,
        key=lambda job: (priority[getattr(job.status, "value", str(job.status))], job.id),
        reverse=False,
    )[:limit]


def active_jobs(jobs: list[ContentJob], limit: int = 5) -> list[ContentJob]:
    return [
        job for job in jobs
        if getattr(job.status, "value", str(job.status)) == "running"
    ][:limit]
