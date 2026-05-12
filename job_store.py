from __future__ import annotations
import json
from pathlib import Path
from models.content_job import ContentJob


def save_job(job: ContentJob) -> Path:
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "job.json"
    path.write_text(job.model_dump_json(indent=2))
    return path


def load_job(job_id: str, page_name: str) -> ContentJob:
    path = Path("output") / page_name / job_id / "job.json"
    if not path.exists():
        raise FileNotFoundError(f"Job not found: {path}")
    return ContentJob.model_validate_json(path.read_text())


def find_job(job_id: str) -> ContentJob:
    for path in Path("output").rglob(f"{job_id}/job.json"):
        return ContentJob.model_validate_json(path.read_text())
    raise FileNotFoundError(f"Job ID '{job_id}' not found in output/")


def load_recent_performance(page_name: str, limit: int = 5) -> str:
    page_dir = Path("output") / page_name
    if not page_dir.exists():
        return ""
    job_files = sorted(page_dir.rglob("job.json"), reverse=True)[:limit]
    lines = []
    for path in job_files:
        try:
            job = ContentJob.model_validate_json(path.read_text())
            for p in job.performance:
                lines.append(
                    f"Job {job.id} ({p.platform}): "
                    f"likes={p.likes}, reach={p.reach}, saves={p.saves}, shares={p.shares}"
                )
        except Exception:
            continue
    if not lines:
        return ""
    return "Past performance data:\n" + "\n".join(lines)
