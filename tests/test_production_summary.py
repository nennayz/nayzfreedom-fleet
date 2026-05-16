from __future__ import annotations

import json
from pathlib import Path

import production_summary
from production_summary import build_summary


def _write_job(
    tmp_path: Path,
    job_id: str,
    status: str = "completed",
    publish_result: dict | None = None,
) -> None:
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
        "brief": "summary",
        "platforms": ["facebook", "instagram"],
        "status": status,
        "stage": "publish_done",
        "dry_run": False,
        "performance": [],
        "checkpoint_log": [],
    }
    if publish_result is not None:
        job["publish_result"] = publish_result
    job_dir = tmp_path / "output" / "Slayhack" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps(job))


def test_build_summary_counts_job_and_publish_states(tmp_path):
    _write_job(
        tmp_path,
        "20260516_060000",
        publish_result={
            "facebook": {"status": "scheduled"},
            "instagram": {"status": "pending_queue"},
        },
    )
    _write_job(
        tmp_path,
        "20260516_070000",
        status="failed",
        publish_result={"instagram": {"status": "failed"}},
    )

    summary = build_summary(tmp_path)

    assert "Slayhack production summary" in summary
    assert "total_jobs=2" in summary
    assert "latest_job=20260516_070000" in summary
    assert "completed=1 failed=1" in summary
    assert "facebook_scheduled=1" in summary
    assert "instagram_pending_queue=1" in summary
    assert "failed=1" in summary


def test_main_defaults_root_to_script_directory(tmp_path, monkeypatch, capsys):
    _write_job(tmp_path, "20260516_060000")
    monkeypatch.setattr(production_summary, "__file__", str(tmp_path / "production_summary.py"))
    monkeypatch.setattr("sys.argv", ["production_summary.py", "--dry-run"])

    production_summary.main()

    out = capsys.readouterr().out
    assert "Slayhack production summary" in out
    assert "total_jobs=1" in out
