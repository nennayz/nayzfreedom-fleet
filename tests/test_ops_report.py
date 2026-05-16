from __future__ import annotations

import json
from pathlib import Path

from ops_report import build_ops_report, write_ops_report_log


def _write_job(tmp_path: Path, job_id: str, status: str = "completed") -> None:
    job = {
        "id": job_id,
        "project": "nayzfreedom_fleet",
        "pm": {
            "name": "Slay",
            "page_name": "Slayhack",
            "persona": "",
            "brand": {
                "mission": "m",
                "visual": {"colors": [], "style": ""},
                "platforms": [],
                "tone": "",
                "target_audience": "",
                "script_style": "",
            },
        },
        "brief": "ops",
        "platforms": ["facebook"],
        "status": status,
        "stage": "publish_done",
        "dry_run": False,
        "performance": [],
        "checkpoint_log": [],
    }
    job_dir = tmp_path / "output" / "Slayhack" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps(job))


def test_build_ops_report_counts_actions_incidents_and_jobs(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "ops_actions.jsonl").write_text(
        json.dumps({"action": "smoke_test"}) + "\n"
        + json.dumps({"action": "production_summary"}) + "\n"
    )
    (logs / "ops_incidents.jsonl").write_text(
        json.dumps({"title": "Queue issue", "status": "open", "severity": "critical"}) + "\n"
        + json.dumps({"title": "Backup checked", "status": "resolved", "severity": "info"}) + "\n"
    )
    _write_job(tmp_path, "20260516_060000")
    _write_job(tmp_path, "20260516_070000", status="failed")

    report = build_ops_report(tmp_path)

    assert "Slayhack weekly Ops report" in report
    assert "ops_actions_total=2" in report
    assert "smoke_test=1" in report
    assert "production_summary=1" in report
    assert "open=1" in report
    assert "resolved=1" in report
    assert "critical=1" in report
    assert "jobs total=2 failed=1 latest=20260516_070000" in report
    assert "recent_failed_jobs=20260516_070000" in report


def test_write_ops_report_log_appends_history(tmp_path):
    report = "Slayhack weekly Ops report\njobs total=1 failed=0 latest=20260516_070000"

    write_ops_report_log(tmp_path, report)

    path = tmp_path / "logs" / "ops_reports.jsonl"
    record = json.loads(path.read_text().splitlines()[-1])
    assert record["title"] == "Slayhack weekly Ops report"
    assert record["line_count"] == 2
    assert record["report"] == report
    assert record["timestamp"]
