from __future__ import annotations
from datetime import date
from pathlib import Path
from unittest.mock import patch

from models.content_job import (
    BrandProfile, ContentJob, JobStatus, PMProfile, VisualIdentity,
)


def _make_pm(page_name: str = "NayzFreedom Fleet") -> PMProfile:
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""),
        platforms=[], tone="", target_audience="", script_style="",
        nora_max_retries=2,
    )
    return PMProfile(name="Test PM", page_name=page_name, persona="", brand=brand)


def _make_job(job_id: str, page_name: str = "NayzFreedom Fleet") -> ContentJob:
    return ContentJob(
        id=job_id, project="nayzfreedom_fleet", pm=_make_pm(page_name),
        brief="test brief", platforms=["facebook"],
        status=JobStatus.COMPLETED,
    )


def _write_job(tmp_path: Path, job: ContentJob) -> None:
    job_dir = tmp_path / "output" / job.pm.page_name / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(job.model_dump_json())


def test_list_all_jobs_no_output_dir_returns_empty(tmp_path):
    from dashboard_store import list_all_jobs
    assert list_all_jobs(tmp_path) == []


def test_list_all_jobs_returns_jobs_sorted_newest_first(tmp_path):
    job1 = _make_job("20260511_060000")
    job2 = _make_job("20260512_060000")
    job3 = _make_job("20260510_060000")
    for j in [job1, job2, job3]:
        _write_job(tmp_path, j)

    from dashboard_store import list_all_jobs
    result = list_all_jobs(tmp_path)
    assert [j.id for j in result] == [
        "20260512_060000", "20260511_060000", "20260510_060000",
    ]


def test_list_all_jobs_skips_corrupt_files(tmp_path):
    valid = _make_job("20260512_060000")
    _write_job(tmp_path, valid)
    corrupt_dir = tmp_path / "output" / "NayzFreedom Fleet" / "20260511_060000"
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    (corrupt_dir / "job.json").write_text("not valid json {{{")

    from dashboard_store import list_all_jobs
    result = list_all_jobs(tmp_path)
    assert len(result) == 1
    assert result[0].id == "20260512_060000"


def test_list_all_jobs_aggregates_multiple_pages(tmp_path):
    job_a = _make_job("20260512_060000", "Page A")
    job_b = _make_job("20260511_060000", "Page B")
    _write_job(tmp_path, job_a)
    _write_job(tmp_path, job_b)

    from dashboard_store import list_all_jobs
    result = list_all_jobs(tmp_path)
    assert len(result) == 2
    assert result[0].id == "20260512_060000"


def test_load_performance_all_delegates_to_collect_week_data(tmp_path):
    fake_data = {"Page A": {}}
    with patch("dashboard_store.collect_week_data", return_value=fake_data) as mock_fn:
        from dashboard_store import load_performance_all
        result = load_performance_all(tmp_path)
    mock_fn.assert_called_once_with(tmp_path, date.today())
    assert result == fake_data


def test_summarize_jobs_counts_statuses():
    from dashboard_store import summarize_jobs
    jobs = [
        _make_job("20260512_060000"),
        _make_job("20260511_060000"),
        _make_job("20260510_060000"),
    ]
    jobs[1].status = JobStatus.RUNNING
    jobs[2].status = JobStatus.FAILED
    assert summarize_jobs(jobs) == {
        "total": 3,
        "completed": 1,
        "running": 1,
        "failed": 1,
        "awaiting_approval": 0,
    }
