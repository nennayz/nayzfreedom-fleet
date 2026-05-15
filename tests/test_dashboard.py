from __future__ import annotations
import base64
import html
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set env vars before dashboard is first imported in this process
os.environ["DASHBOARD_USER"] = "admin"
os.environ["DASHBOARD_PASSWORD"] = "secret"

import dashboard as _dm  # noqa: E402


def _auth(user: str = "admin", pw: str = "secret") -> dict:
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _make_pm_dict(page_name: str = "NayzFreedom Fleet") -> dict:
    return {
        "name": "Test PM", "page_name": page_name, "persona": "",
        "brand": {
            "mission": "m", "visual": {"colors": [], "style": ""},
            "platforms": [], "tone": "", "target_audience": "",
            "script_style": "", "nora_max_retries": 2,
        },
    }


def _write_job(tmp_path: Path, job_id: str, brief: str = "test brief",
               status: str = "completed", page: str = "NayzFreedom Fleet",
               stage: str = "init") -> None:
    job = {
        "id": job_id, "project": "nayzfreedom_fleet", "pm": _make_pm_dict(page),
        "brief": brief, "platforms": ["facebook"], "status": status,
        "stage": stage, "dry_run": False, "performance": [], "checkpoint_log": [],
    }
    job_dir = tmp_path / "output" / page / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(json.dumps(job))


@pytest.fixture
def client(tmp_path):
    _dm.app.state.root = tmp_path
    return TestClient(_dm.app, raise_server_exceptions=True)


def test_dashboard_requires_auth(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 401


def test_dashboard_wrong_credentials(client):
    resp = client.get("/", headers=_auth("admin", "wrong"))
    assert resp.status_code == 401


def test_captains_deck_empty(client):
    resp = client.get("/", headers=_auth())
    assert resp.status_code == 200
    assert "Captain's Deck" in resp.text
    assert "No missions yet" in resp.text


def test_captains_deck_shows_recent_mission(tmp_path, client):
    _write_job(tmp_path, "20260512_060000", brief="luxury brands rock")
    resp = client.get("/", headers=_auth())
    assert resp.status_code == 200
    assert "luxury brands rock" in resp.text


def test_aurora_overview_shows_projects(tmp_path, client):
    (tmp_path / "projects" / "nayzfreedom_fleet").mkdir(parents=True)
    (tmp_path / "projects" / "nayzfreedom_fleet" / "pm_profile.yaml").write_text("page_name: test\n")
    resp = client.get("/aurora", headers=_auth())
    assert resp.status_code == 200
    assert "The Aurora" in resp.text
    assert "test" in resp.text
    assert "/aurora/islands/nayzfreedom_fleet" in resp.text


def test_aurora_crew_pages_render(client):
    crew = client.get("/aurora/crew", headers=_auth())
    detail = client.get("/aurora/crew/robin", headers=_auth())
    assert crew.status_code == 200
    assert "Crew" in crew.text
    assert "Robin" in crew.text
    assert "Mission command" in crew.text
    assert "Captain&#39;s Bridge" in crew.text
    assert detail.status_code == 200
    assert "Chief Officer" in detail.text
    assert "Operational contract" in detail.text
    assert "command coat" in detail.text


def test_aurora_all_crew_character_sheets_render(client):
    from crew_registry import CREW

    for member in CREW:
        resp = client.get(f"/aurora/crew/{member.slug}", headers=_auth())
        assert resp.status_code == 200
        text = html.unescape(resp.text)
        assert member.name in resp.text
        assert member.workflow_stage in resp.text
        assert member.station in text


def test_aurora_crew_detail_unknown_member_404(client):
    resp = client.get("/aurora/crew/unknown", headers=_auth())
    assert resp.status_code == 404


def test_island_detail_renders(tmp_path, client, monkeypatch):
    (tmp_path / "projects" / "nayzfreedom_fleet").mkdir(parents=True)
    (tmp_path / "projects" / "nayzfreedom_fleet" / "pm_profile.yaml").write_text(
        'name: "Slay"\npage_name: "NayzFreedom Fleet"\npersona: "bold persona"\n'
    )
    (tmp_path / "projects" / "nayzfreedom_fleet" / "brand.yaml").write_text(
        'mission: "mission"\nvisual:\n  colors: ["#fff"]\n  style: "minimal"\n'
        'platforms: ["instagram"]\ntone: "sassy"\ntarget_audience: "women"\n'
        'script_style: "lowercase"\nallowed_content_types: ["video", "image"]\n'
    )
    _write_job(tmp_path, "20260512_060000", brief="island mission", status="completed")
    _write_job(tmp_path, "20260512_070000", brief="attention mission", status="failed")
    monkeypatch.chdir(tmp_path)
    resp = client.get("/aurora/islands/nayzfreedom_fleet", headers=_auth())
    assert resp.status_code == 200
    assert "NayzFreedom Fleet" in resp.text
    assert "mission" in resp.text
    assert "Launch island mission" in resp.text
    assert "/aurora/new-mission?project=nayzfreedom_fleet" in resp.text
    assert "island mission" in resp.text
    assert "Needs attention" in resp.text
    assert "bold persona" in resp.text
    assert "video" in resp.text
    assert "image" in resp.text


def test_new_mission_preselects_project(tmp_path, client):
    for slug in ("alpha", "nayzfreedom_fleet"):
        (tmp_path / "projects" / slug).mkdir(parents=True)
        (tmp_path / "projects" / slug / "pm_profile.yaml").write_text("page_name: test\n")
    resp = client.get("/aurora/new-mission?project=nayzfreedom_fleet", headers=_auth())
    assert resp.status_code == 200
    assert '<option value="nayzfreedom_fleet" selected>test</option>' in resp.text


def test_placeholder_ship_pages_render(client):
    freedom = client.get("/freedom", headers=_auth())
    lyra = client.get("/lyra", headers=_auth())
    assert freedom.status_code == 200
    assert "Freedom Five" in freedom.text
    assert lyra.status_code == 200
    assert "Song voyage" in lyra.text


def test_jobs_partial_returns_fragment(tmp_path, client):
    _write_job(tmp_path, "20260512_060000")
    resp = client.get("/jobs/partial", headers=_auth())
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "<tbody" in resp.text


def test_dashboard_refuses_start_without_env():
    saved_user = os.environ.pop("DASHBOARD_USER", None)
    saved_pass = os.environ.pop("DASHBOARD_PASSWORD", None)
    sys.modules.pop("dashboard", None)
    try:
        with pytest.raises(RuntimeError):
            import dashboard  # noqa: F401
    finally:
        if saved_user is not None:
            os.environ["DASHBOARD_USER"] = saved_user
        if saved_pass is not None:
            os.environ["DASHBOARD_PASSWORD"] = saved_pass
        sys.modules.pop("dashboard", None)
        import dashboard  # noqa: F401  # re-import cleanly for subsequent tests


def test_job_detail_404(client):
    with patch.object(_dm, "find_job", side_effect=FileNotFoundError("not found")):
        resp = client.get("/jobs/nonexistent_id", headers=_auth())
    assert resp.status_code == 404


def test_job_detail_shows_brief(tmp_path, client):
    _write_job(tmp_path, "20260512_060000", brief="luxury brands are amazing")
    from models.content_job import ContentJob
    job = ContentJob.model_validate_json(
        (tmp_path / "output" / "NayzFreedom Fleet" / "20260512_060000" / "job.json").read_text()
    )
    with patch.object(_dm, "find_job", return_value=job):
        resp = client.get("/jobs/20260512_060000", headers=_auth())
    assert resp.status_code == 200
    assert "luxury brands are amazing" in resp.text
    assert "Voyage log" in resp.text
    assert "Command the Brief" in resp.text
    assert "/aurora/crew/robin" in resp.text


def test_job_detail_workflow_marks_current_crew_stage(tmp_path, client):
    _write_job(
        tmp_path,
        "20260512_070000",
        brief="visual stage mission",
        status="running",
        stage="lila_done",
    )
    from models.content_job import ContentJob
    job = ContentJob.model_validate_json(
        (tmp_path / "output" / "NayzFreedom Fleet" / "20260512_070000" / "job.json").read_text()
    )
    with patch.object(_dm, "find_job", return_value=job):
        resp = client.get("/jobs/20260512_070000", headers=_auth())
    assert resp.status_code == 200
    assert "Shape the Vision" in resp.text
    assert "Lila Lens" in resp.text
    assert "Studio Deck" in resp.text
    assert "timeline-step current" in resp.text
    assert "/aurora/crew/lila" in resp.text


def test_metrics_no_data(client):
    resp = client.get("/metrics", headers=_auth())
    assert resp.status_code == 200
    assert "No performance data" in resp.text


def test_metrics_shows_data(client):
    from reporter import PlatformStats
    fake_data = {
        "NayzFreedom Fleet": {
            "facebook": PlatformStats(job_count=3, total_reach=5000, total_likes=120),
        }
    }
    with patch.object(_dm, "load_performance_all", return_value=fake_data):
        resp = client.get("/metrics", headers=_auth())
    assert resp.status_code == 200
    assert "NayzFreedom Fleet" in resp.text
    assert "5,000" in resp.text


def test_trigger_get_shows_form(tmp_path, client):
    (tmp_path / "projects" / "nayzfreedom_fleet").mkdir(parents=True)
    (tmp_path / "projects" / "nayzfreedom_fleet" / "pm_profile.yaml").write_text("page_name: test\n")
    resp = client.get("/trigger", headers=_auth())
    assert resp.status_code == 200
    assert "<form" in resp.text
    assert '<option value="nayzfreedom_fleet" selected>test</option>' in resp.text


def test_trigger_spawns_subprocess(tmp_path, client):
    (tmp_path / "projects" / "nayzfreedom_fleet").mkdir(parents=True)
    (tmp_path / "projects" / "nayzfreedom_fleet" / "pm_profile.yaml").write_text("page_name: test\n")
    mock_popen = MagicMock()
    with patch("dashboard.subprocess.Popen", mock_popen):
        resp = client.post(
            "/trigger",
            data={"project": "nayzfreedom_fleet", "brief": "test brief", "content_type": "video"},
            headers=_auth(),
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/aurora/missions"
    mock_popen.assert_called_once()
    cmd = mock_popen.call_args.args[0]
    assert "main.py" in cmd
    assert "--project" in cmd
    assert "nayzfreedom_fleet" in cmd
    assert "--unattended" in cmd
    assert "--dry-run" not in cmd


def test_trigger_dry_run_adds_flag(tmp_path, client):
    (tmp_path / "projects" / "nayzfreedom_fleet").mkdir(parents=True)
    (tmp_path / "projects" / "nayzfreedom_fleet" / "pm_profile.yaml").write_text("page_name: test\n")
    mock_popen = MagicMock()
    with patch("dashboard.subprocess.Popen", mock_popen):
        resp = client.post(
            "/trigger",
            data={"project": "nayzfreedom_fleet", "brief": "test", "content_type": "video", "dry_run": "1"},
            headers=_auth(),
            follow_redirects=False,
        )
    assert resp.status_code == 303
    cmd = mock_popen.call_args.args[0]
    assert "--dry-run" in cmd


def test_trigger_rejects_unknown_project(client):
    resp = client.post(
        "/trigger",
        data={"project": "nonexistent", "brief": "test", "content_type": "video"},
        headers=_auth(),
    )
    assert resp.status_code == 400
