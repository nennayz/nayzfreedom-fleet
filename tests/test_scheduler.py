from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from unittest.mock import call, patch, MagicMock
import pytest
import scheduler as sched_module


MONDAY_CALENDAR = {
    "monday": {
        "short_video_1": "15-40sec Reel: morning routine",
        "short_video_2": "15-40sec Reel: 5 outfit ideas",
        "long_video": "1-3min video: wardrobe guide",
        "article_1": "quiet luxury brands",
        "article_2": "old money style",
        "infographic_1": "color palette guide",
        "infographic_2": "capsule wardrobe checklist",
    }
}


def _make_ok_result():
    r = MagicMock()
    r.returncode = 0
    return r


def _make_fail_result():
    r = MagicMock()
    r.returncode = 1
    return r


def test_scheduler_loads_todays_brief(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False, root=tmp_path)
    assert exit_code == 0
    assert mock_run.call_count == 7
    calls_flat = [c.args[0] for c in mock_run.call_args_list]
    assert any("--content-type" in str(c) and "video" in str(c) for c in calls_flat)
    assert any("--content-type" in str(c) and "article" in str(c) for c in calls_flat)
    assert any("--content-type" in str(c) and "infographic" in str(c) for c in calls_flat)


def test_scheduler_skips_missing_day(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump({"monday": MONDAY_CALENDAR["monday"]})
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "tuesday")
    with patch("scheduler.subprocess.run") as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False, root=tmp_path)
    assert mock_run.call_count == 0
    assert exit_code == 0


def test_scheduler_skips_blank_brief(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    calendar = {"monday": dict(MONDAY_CALENDAR["monday"])}
    calendar["monday"]["short_video_1"] = ""
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(calendar)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False, root=tmp_path)
    assert mock_run.call_count == 6


def test_scheduler_continues_after_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    results = [_make_fail_result()] + [_make_ok_result()] * 6
    with patch("scheduler.subprocess.run", side_effect=results) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False, root=tmp_path)
    assert mock_run.call_count == 7
    assert exit_code == 1


def test_scheduler_dry_run_passes_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()) as mock_run:
        sched_module.run_scheduler(dry_run=True, root=tmp_path)
    for c in mock_run.call_args_list:
        assert "--dry-run" in c.args[0]


def test_scheduler_exit_code_zero_on_all_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()):
        exit_code = sched_module.run_scheduler(dry_run=False, root=tmp_path)
    assert exit_code == 0


def test_scheduler_timeout_continues_and_sets_exit_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    mock_proc = MagicMock()
    timeout_exc = subprocess.TimeoutExpired(cmd=[], timeout=1800)
    timeout_exc.process = mock_proc
    side_effects = [timeout_exc] + [_make_ok_result()] * 6
    with patch("scheduler.subprocess.run", side_effect=side_effects) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False, root=tmp_path)
    assert mock_run.call_count == 7
    assert exit_code == 1
    mock_proc.kill.assert_called_once()


def test_scheduler_calls_notifier_on_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    results = [_make_fail_result()] + [_make_ok_result()] * 6
    with patch("scheduler.subprocess.run", side_effect=results), \
         patch("scheduler.send_slack_alert") as mock_alert:
        sched_module.run_scheduler(dry_run=False, root=tmp_path)
    mock_alert.assert_called_once()
    failures = mock_alert.call_args.args[0]
    assert len(failures) == 1
    assert failures[0]["project"] == "slay_hack"
    assert failures[0]["brief"] == "short_video_1"
    assert failures[0]["content_type"] == "video"
    assert failures[0]["exit_code"] == 1


def test_scheduler_does_not_call_notifier_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()), \
         patch("scheduler.send_slack_alert") as mock_alert:
        sched_module.run_scheduler(dry_run=False, root=tmp_path)
    mock_alert.assert_not_called()
