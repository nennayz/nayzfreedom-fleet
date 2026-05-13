from __future__ import annotations
import base64
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


def _make_pm_dict(page_name: str = "Slay Hack Agency") -> dict:
    return {
        "name": "Test PM", "page_name": page_name, "persona": "",
        "brand": {
            "mission": "m", "visual": {"colors": [], "style": ""},
            "platforms": [], "tone": "", "target_audience": "",
            "script_style": "", "nora_max_retries": 2,
        },
    }


def _write_job(tmp_path: Path, job_id: str, brief: str = "test brief",
               status: str = "completed", page: str = "Slay Hack Agency") -> None:
    job = {
        "id": job_id, "project": "slay_hack", "pm": _make_pm_dict(page),
        "brief": brief, "platforms": ["facebook"], "status": status,
        "stage": "init", "dry_run": False, "performance": [], "checkpoint_log": [],
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


def test_jobs_list_empty(client):
    resp = client.get("/", headers=_auth())
    assert resp.status_code == 200
    assert "No jobs yet" in resp.text


def test_jobs_list_shows_job(tmp_path, client):
    _write_job(tmp_path, "20260512_060000", brief="luxury brands rock")
    resp = client.get("/", headers=_auth())
    assert resp.status_code == 200
    assert "luxury brands rock" in resp.text


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
