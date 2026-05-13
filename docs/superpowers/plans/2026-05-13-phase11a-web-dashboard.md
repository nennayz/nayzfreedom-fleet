# Phase 11a: Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + HTMX web dashboard for viewing job history, performance metrics, and triggering new pipeline runs from a browser — replacing SSH/terminal access for day-to-day operations.

**Architecture:** FastAPI app with Jinja2 templates and HTTP Basic Auth on every route. `dashboard_store.py` provides two helper functions (list all jobs, load weekly performance) that wrap existing `reporter.py` and `job_store.py`. HTMX auto-polls the jobs list while any job is `RUNNING`; the partial `/jobs/partial` route returns only the `<tbody>` fragment. All frontend dependencies (HTMX) are vendored locally in `static/`.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, python-multipart, HTMX 1.9.x (vendored as `static/htmx.min.js`), FastAPI `TestClient` (pytest)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add fastapi, uvicorn[standard], jinja2, python-multipart |
| `.env.example` | Modify | Add DASHBOARD_USER, DASHBOARD_PASSWORD |
| `CLAUDE.md` | Modify | Add dashboard run commands |
| `static/htmx.min.js` | Create | Vendored HTMX (downloaded via curl) |
| `static/style.css` | Create | Minimal dashboard CSS |
| `dashboard_store.py` | Create | `list_all_jobs(root)`, `load_performance_all(root)` |
| `templates/base.html` | Create | Shared layout, nav, loads htmx + css |
| `templates/_jobs_partial.html` | Create | `<tbody>` fragment for HTMX auto-poll |
| `templates/jobs.html` | Create | Full jobs list page |
| `templates/job_detail.html` | Create | Job detail with collapsible sections |
| `templates/metrics.html` | Create | Performance table per brand page |
| `templates/trigger.html` | Create | Trigger form with confirm dialog |
| `dashboard.py` | Create | FastAPI app, all routes, auth, CLI |
| `tests/test_dashboard_store.py` | Create | Tests for list_all_jobs, load_performance_all |
| `tests/test_dashboard.py` | Create | Tests for all routes via TestClient |

---

## Task 1: Dependencies, env setup, vendor htmx.min.js

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `CLAUDE.md`
- Create: `static/htmx.min.js`

- [ ] **Step 1: Add FastAPI dependencies to requirements.txt**

Append these 4 lines to `requirements.txt` (after the existing entries):
```
fastapi
uvicorn[standard]
jinja2
python-multipart
```

- [ ] **Step 2: Install new dependencies**

Run: `pip install fastapi "uvicorn[standard]" jinja2 python-multipart`
Expected: All 4 packages install without error.

- [ ] **Step 3: Add env vars to .env.example**

Append to `.env.example`:
```
DASHBOARD_USER=
DASHBOARD_PASSWORD=
```

- [ ] **Step 4: Add dashboard run commands to CLAUDE.md**

In the `## Common Commands` section, append:
```bash
# Run dashboard (local only)
python dashboard.py

# Dashboard on VPS (accessible from outside)
python dashboard.py --host 0.0.0.0 --port 8000
```

- [ ] **Step 5: Create static/ directory and vendor htmx.min.js**

Run:
```bash
mkdir -p static
curl -sL https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js -o static/htmx.min.js
```
Expected: `static/htmx.min.js` created. Verify: `ls -lh static/htmx.min.js` — should show ~50 KB.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example CLAUDE.md static/htmx.min.js
git commit -m "feat: add Phase 11a dependencies and vendor htmx.min.js"
```

---

## Task 2: dashboard_store.py

**Files:**
- Create: `dashboard_store.py`
- Create: `tests/test_dashboard_store.py`

Two functions not in `job_store.py`:
- `list_all_jobs(root)` — scan `output/<page>/<job_id>/job.json`, return all jobs sorted newest first
- `load_performance_all(root)` — delegate to `reporter.collect_week_data(root, date.today())`

- [ ] **Step 1: Write failing tests**

Create `tests/test_dashboard_store.py`:
```python
from __future__ import annotations
from datetime import date
from pathlib import Path
from unittest.mock import patch

from models.content_job import (
    BrandProfile, ContentJob, JobStatus, PMProfile, VisualIdentity,
)


def _make_pm(page_name: str = "Slay Hack Agency") -> PMProfile:
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""),
        platforms=[], tone="", target_audience="", script_style="",
        nora_max_retries=2,
    )
    return PMProfile(name="Test PM", page_name=page_name, persona="", brand=brand)


def _make_job(job_id: str, page_name: str = "Slay Hack Agency") -> ContentJob:
    return ContentJob(
        id=job_id, project="slay_hack", pm=_make_pm(page_name),
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
    corrupt_dir = tmp_path / "output" / "Slay Hack Agency" / "20260511_060000"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard_store.py -v`
Expected: `ModuleNotFoundError: No module named 'dashboard_store'`

- [ ] **Step 3: Implement dashboard_store.py**

Create `dashboard_store.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard_store.py -v`
Expected: 5/5 PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest`
Expected: All existing tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add dashboard_store.py tests/test_dashboard_store.py
git commit -m "feat: add dashboard_store with list_all_jobs and load_performance_all"
```

---

## Task 3: Templates

**Files:**
- Create: `templates/base.html`
- Create: `templates/_jobs_partial.html`
- Create: `templates/jobs.html`
- Create: `templates/job_detail.html`
- Create: `templates/metrics.html`
- Create: `templates/trigger.html`

Templates are created before routes so the TestClient can render full HTML in Tasks 4–7. `_jobs_partial.html` is an extra file (not in spec's list of 5) that holds the `<tbody>` fragment used by both `GET /` and `GET /jobs/partial`. Status badge CSS classes: `badge-completed` (green), `badge-running` (yellow), `badge-failed` (red), `badge-pending` (grey).

- [ ] **Step 1: Create templates/ directory**

Run: `mkdir -p templates`

- [ ] **Step 2: Create base.html**

Create `templates/base.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NayzFreedom Dashboard</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/htmx.min.js"></script>
</head>
<body>
<nav>
  <a href="/">Jobs</a>
  <a href="/metrics">Metrics</a>
  <a href="/trigger">New Run</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

- [ ] **Step 3: Create _jobs_partial.html (tbody fragment)**

Create `templates/_jobs_partial.html`:
```html
{% set has_running = jobs | selectattr("status", "equalto", "running") | list %}
<tbody{% if has_running %} hx-get="/jobs/partial" hx-trigger="every 10s" hx-swap="outerHTML"{% endif %}>
{% for job in jobs %}
<tr>
  <td>{{ job.id[:8] }}</td>
  <td><a href="/jobs/{{ job.id }}">{{ job.project }}</a></td>
  <td>{{ job.brief[:60] }}{% if job.brief | length > 60 %}…{% endif %}</td>
  <td>{{ job.content_type or "" }}</td>
  <td><span class="badge badge-{{ job.status }}">{{ job.status }}</span></td>
  <td>{{ job.stage }}</td>
</tr>
{% endfor %}
</tbody>
```

- [ ] **Step 4: Create jobs.html**

Create `templates/jobs.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1>Jobs</h1>
{% if jobs %}
<table>
  <thead>
    <tr>
      <th>Date</th>
      <th>Project</th>
      <th>Brief</th>
      <th>Content Type</th>
      <th>Status</th>
      <th>Stage</th>
    </tr>
  </thead>
  {% include "_jobs_partial.html" %}
</table>
{% else %}
<p>No jobs yet.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Create job_detail.html**

Create `templates/job_detail.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1>Job: {{ job.id }}</h1>
<p><strong>Project:</strong> {{ job.project }}</p>
<p><strong>Brief:</strong> {{ job.brief }}</p>
<p><strong>Platforms:</strong> {{ job.platforms | join(", ") }}</p>
<p><strong>Content Type:</strong> {{ job.content_type or "—" }}</p>
<p><strong>Status:</strong> <span class="badge badge-{{ job.status }}">{{ job.status }}</span></p>
<p><strong>Stage:</strong> {{ job.stage }}</p>

{% if job.bella_output %}
<details>
  <summary>Script</summary>
  {% if job.bella_output.type == "script" %}
  <p><strong>Hook:</strong> {{ job.bella_output.hook }}</p>
  <p><strong>Body:</strong> {{ job.bella_output.body }}</p>
  <p><strong>CTA:</strong> {{ job.bella_output.cta }}</p>
  {% elif job.bella_output.type == "article" %}
  <p><strong>Heading:</strong> {{ job.bella_output.heading }}</p>
  <p><strong>Body:</strong> {{ job.bella_output.body }}</p>
  <p><strong>CTA:</strong> {{ job.bella_output.cta }}</p>
  {% elif job.bella_output.type == "image" %}
  <p><strong>Caption:</strong> {{ job.bella_output.caption }}</p>
  {% elif job.bella_output.type == "infographic" %}
  <p><strong>Title:</strong> {{ job.bella_output.title }}</p>
  {% endif %}
</details>
{% endif %}

{% if job.growth_strategy %}
<details>
  <summary>Caption + Hashtags</summary>
  <p>{{ job.growth_strategy.caption }}</p>
  <p>{{ job.growth_strategy.hashtags | join(" ") }}</p>
</details>
{% endif %}

{% if faq_content %}
<details>
  <summary>FAQ</summary>
  <pre>{{ faq_content }}</pre>
</details>
{% endif %}

{% if job.visual_prompt %}
<details>
  <summary>Visual Prompt</summary>
  <p>{{ job.visual_prompt }}</p>
</details>
{% endif %}

{% if job.checkpoint_log %}
<details>
  <summary>Checkpoint Log</summary>
  <ul>
  {% for c in job.checkpoint_log %}
    <li>{{ c.stage }}: {{ c.decision }} ({{ c.timestamp }})</li>
  {% endfor %}
  </ul>
</details>
{% endif %}

{% if job.publish_result %}
<details>
  <summary>Publish Result</summary>
  <pre>{{ job.publish_result }}</pre>
</details>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Create metrics.html**

Create `templates/metrics.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1>Performance (Last 7 Days)</h1>
{% if data %}
{% for page_name, platforms in data.items() %}
<h2>{{ page_name }}</h2>
<table>
  <thead>
    <tr>
      <th>Platform</th><th>Jobs</th><th>Reach</th>
      <th>Likes</th><th>Saves</th><th>Shares</th><th>Top Post</th>
    </tr>
  </thead>
  <tbody>
  {% for platform, stats in platforms.items() %}
    <tr>
      <td>{{ platform }}</td>
      <td>{{ stats.job_count }}</td>
      <td>{{ "{:,}".format(stats.total_reach) }}</td>
      <td>{{ "{:,}".format(stats.total_likes) }}</td>
      <td>{{ "{:,}".format(stats.total_saves) }}</td>
      <td>{{ "{:,}".format(stats.total_shares) }}</td>
      <td>
        {% if stats.top_job_id %}
        <a href="/jobs/{{ stats.top_job_id }}">{{ stats.top_job_brief[:40] }}</a>
        {% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endfor %}
{% else %}
<p>No performance data for the last 7 days.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Create trigger.html**

Create `templates/trigger.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1>New Run</h1>
<form method="post" action="/trigger" onsubmit="return confirm('Start this pipeline run?')">
  <div>
    <label for="project">Project</label>
    <select name="project" id="project" required>
      {% for slug in projects %}
      <option value="{{ slug }}">{{ slug }}</option>
      {% endfor %}
    </select>
  </div>
  <div>
    <label for="content_type">Content Type</label>
    <select name="content_type" id="content_type" required>
      <option value="video">video</option>
      <option value="article">article</option>
      <option value="image">image</option>
      <option value="infographic">infographic</option>
    </select>
  </div>
  <div>
    <label for="brief">Brief</label>
    <textarea name="brief" id="brief" required rows="4"></textarea>
  </div>
  <div>
    <label>
      <input type="checkbox" name="dry_run" value="1" checked>
      Dry Run
    </label>
  </div>
  <button type="submit">Start Pipeline</button>
</form>
{% endblock %}
```

- [ ] **Step 8: Commit**

```bash
git add templates/
git commit -m "feat: add Jinja2 templates for all dashboard pages"
```

---

## Task 4: dashboard.py — app setup, auth, GET /, GET /jobs/partial

**Files:**
- Create: `dashboard.py`
- Create: `tests/test_dashboard.py`

**Key constraint:** `DASHBOARD_USER` and `DASHBOARD_PASSWORD` are read at module import time. If either is missing, the module raises `RuntimeError` immediately. Tests must set these env vars before importing `dashboard`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_dashboard.py`:
```python
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
        if saved_user:
            os.environ["DASHBOARD_USER"] = saved_user
        if saved_pass:
            os.environ["DASHBOARD_PASSWORD"] = saved_pass
        sys.modules.pop("dashboard", None)
        import dashboard  # noqa: F401  # re-import cleanly for subsequent tests
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard.py -v`
Expected: `ModuleNotFoundError: No module named 'dashboard'`

- [ ] **Step 3: Implement dashboard.py (core + auth + GET / + GET /jobs/partial)**

Create `dashboard.py`:
```python
from __future__ import annotations
import os
import secrets
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DASHBOARD_USER = os.environ.get("DASHBOARD_USER")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
if not DASHBOARD_USER or not DASHBOARD_PASSWORD:
    raise RuntimeError(
        "DASHBOARD_USER and DASHBOARD_PASSWORD must be set in environment before starting the dashboard."
    )

_ROOT = Path(__file__).resolve().parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(_ROOT / "templates"))
security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    correct_user = secrets.compare_digest(credentials.username, DASHBOARD_USER)
    correct_pass = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def _root(request: Request) -> Path:
    return getattr(request.app.state, "root", _ROOT)


@app.get("/", response_class=HTMLResponse)
def jobs_list(request: Request, _: str = Depends(verify_auth)):
    from dashboard_store import list_all_jobs
    jobs = list_all_jobs(_root(request))
    return templates.TemplateResponse("jobs.html", {"request": request, "jobs": jobs})


@app.get("/jobs/partial", response_class=HTMLResponse)
def jobs_partial(request: Request, _: str = Depends(verify_auth)):
    from dashboard_store import list_all_jobs
    jobs = list_all_jobs(_root(request))
    return templates.TemplateResponse("_jobs_partial.html", {"request": request, "jobs": jobs})


if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("dashboard:app", host=args.host, port=args.port, reload=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard.py -v`
Expected: 6/6 PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: add dashboard.py with auth, GET / and GET /jobs/partial"
```

---

## Task 5: GET /jobs/{job_id} — Job detail

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

`find_job` in `job_store.py` uses `Path("output").rglob(...)` which is relative to CWD — not to `app.state.root`. Tests must patch `dashboard.find_job` directly.

- [ ] **Step 1: Add failing tests to tests/test_dashboard.py**

Append to `tests/test_dashboard.py`:
```python
def test_job_detail_404(client):
    with patch("dashboard.find_job", side_effect=FileNotFoundError("not found")):
        resp = client.get("/jobs/nonexistent_id", headers=_auth())
    assert resp.status_code == 404


def test_job_detail_shows_brief(tmp_path, client):
    _write_job(tmp_path, "20260512_060000", brief="luxury brands are amazing")
    from models.content_job import ContentJob
    job = ContentJob.model_validate_json(
        (tmp_path / "output" / "Slay Hack Agency" / "20260512_060000" / "job.json").read_text()
    )
    with patch("dashboard.find_job", return_value=job):
        resp = client.get("/jobs/20260512_060000", headers=_auth())
    assert resp.status_code == 200
    assert "luxury brands are amazing" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard.py::test_job_detail_404 tests/test_dashboard.py::test_job_detail_shows_brief -v`
Expected: FAIL — 404 returned (route doesn't exist yet, FastAPI returns 404 for unknown paths).

Note: `test_job_detail_404` may appear to pass by accident since FastAPI returns 404 for unknown routes. Confirm `test_job_detail_shows_brief` fails — it should get a 404, not 200.

- [ ] **Step 3: Add imports and job detail route to dashboard.py**

At the top of `dashboard.py`, after existing imports, add:
```python
from fastapi.responses import HTMLResponse, RedirectResponse
from job_store import find_job
```

Add the route after `/jobs/partial`:
```python
@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: str, request: Request, _: str = Depends(verify_auth)):
    try:
        job = find_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    root = _root(request)
    faq_path = root / "output" / job.pm.page_name / job_id / "faq.md"
    faq_content = faq_path.read_text() if faq_path.exists() else None
    return templates.TemplateResponse(
        "job_detail.html", {"request": request, "job": job, "faq_content": faq_content}
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard.py::test_job_detail_404 tests/test_dashboard.py::test_job_detail_shows_brief -v`
Expected: 2/2 PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: add GET /jobs/{job_id} job detail route"
```

---

## Task 6: GET /metrics

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing tests to tests/test_dashboard.py**

Append to `tests/test_dashboard.py`:
```python
def test_metrics_no_data(client):
    resp = client.get("/metrics", headers=_auth())
    assert resp.status_code == 200
    assert "No performance data" in resp.text


def test_metrics_shows_data(client):
    from reporter import PlatformStats
    fake_data = {
        "Slay Hack Agency": {
            "facebook": PlatformStats(job_count=3, total_reach=5000, total_likes=120),
        }
    }
    with patch("dashboard.load_performance_all", return_value=fake_data):
        resp = client.get("/metrics", headers=_auth())
    assert resp.status_code == 200
    assert "Slay Hack Agency" in resp.text
    assert "5,000" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard.py::test_metrics_no_data tests/test_dashboard.py::test_metrics_shows_data -v`
Expected: FAIL — route doesn't exist (404).

- [ ] **Step 3: Add metrics route to dashboard.py**

Add import at the top of `dashboard.py` (alongside other imports):
```python
from dashboard_store import list_all_jobs, load_performance_all
```

Remove the `from dashboard_store import list_all_jobs` lines inside the route functions (they were deferred imports) and use the top-level import. Also add the metrics route after `/jobs/{job_id}`:

```python
@app.get("/metrics", response_class=HTMLResponse)
def metrics(request: Request, _: str = Depends(verify_auth)):
    data = load_performance_all(_root(request))
    return templates.TemplateResponse("metrics.html", {"request": request, "data": data})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard.py::test_metrics_no_data tests/test_dashboard.py::test_metrics_shows_data -v`
Expected: 2/2 PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: add GET /metrics performance table route"
```

---

## Task 7: GET /trigger + POST /trigger

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

POST /trigger validates the project against `projects/*/pm_profile.yaml`, then spawns `subprocess.Popen` non-blocking and redirects to `/`.

- [ ] **Step 1: Add failing tests to tests/test_dashboard.py**

Append to `tests/test_dashboard.py`:
```python
def test_trigger_get_shows_form(tmp_path, client):
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    (tmp_path / "projects" / "slay_hack" / "pm_profile.yaml").write_text("page_name: test\n")
    resp = client.get("/trigger", headers=_auth())
    assert resp.status_code == 200
    assert "<form" in resp.text
    assert "slay_hack" in resp.text


def test_trigger_spawns_subprocess(tmp_path, client):
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    (tmp_path / "projects" / "slay_hack" / "pm_profile.yaml").write_text("page_name: test\n")
    mock_popen = MagicMock()
    with patch("dashboard.subprocess.Popen", mock_popen):
        resp = client.post(
            "/trigger",
            data={"project": "slay_hack", "brief": "test brief", "content_type": "video"},
            headers=_auth(),
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    mock_popen.assert_called_once()
    cmd = mock_popen.call_args.args[0]
    assert "main.py" in cmd
    assert "--project" in cmd
    assert "slay_hack" in cmd
    assert "--unattended" in cmd
    assert "--dry-run" not in cmd


def test_trigger_dry_run_adds_flag(tmp_path, client):
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    (tmp_path / "projects" / "slay_hack" / "pm_profile.yaml").write_text("page_name: test\n")
    mock_popen = MagicMock()
    with patch("dashboard.subprocess.Popen", mock_popen):
        resp = client.post(
            "/trigger",
            data={"project": "slay_hack", "brief": "test", "content_type": "video", "dry_run": "1"},
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard.py::test_trigger_get_shows_form tests/test_dashboard.py::test_trigger_spawns_subprocess tests/test_dashboard.py::test_trigger_dry_run_adds_flag tests/test_dashboard.py::test_trigger_rejects_unknown_project -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Add trigger routes to dashboard.py**

Add imports at the top of `dashboard.py`:
```python
import subprocess
from fastapi import Form
```

Add after `/metrics`:
```python
@app.get("/trigger", response_class=HTMLResponse)
def trigger_form(request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    projects = sorted(p.parent.name for p in root.glob("projects/*/pm_profile.yaml"))
    return templates.TemplateResponse(
        "trigger.html", {"request": request, "projects": projects}
    )


@app.post("/trigger")
def trigger_run(
    request: Request,
    project: str = Form(...),
    brief: str = Form(...),
    content_type: str = Form(...),
    dry_run: str = Form(default=None),
    _: str = Depends(verify_auth),
):
    root = _root(request)
    valid = {p.parent.name for p in root.glob("projects/*/pm_profile.yaml")}
    if project not in valid:
        raise HTTPException(status_code=400, detail="Unknown project")
    cmd = [
        sys.executable, "main.py",
        "--project", project,
        "--brief", brief,
        "--content-type", content_type,
        "--unattended",
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.Popen(cmd, cwd=str(_ROOT))
    return RedirectResponse("/", status_code=303)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard.py::test_trigger_get_shows_form tests/test_dashboard.py::test_trigger_spawns_subprocess tests/test_dashboard.py::test_trigger_dry_run_adds_flag tests/test_dashboard.py::test_trigger_rejects_unknown_project -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: add GET/POST /trigger routes for non-blocking pipeline spawn"
```

---

## Task 8: static/style.css

**Files:**
- Create: `static/style.css`

No TDD cycle — CSS is visual. Status badge classes must match `JobStatus` string values: `badge-completed`, `badge-running`, `badge-failed`, `badge-pending`, `badge-awaiting_approval`.

- [ ] **Step 1: Create static/style.css**

Create `static/style.css`:
```css
*, *::before, *::after { box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #fff;
  color: #222;
  margin: 0;
  padding: 0;
}

nav {
  background: #1a1a2e;
  padding: 0.75rem 1.5rem;
  display: flex;
  gap: 1.5rem;
}

nav a {
  color: #e0e0e0;
  text-decoration: none;
  font-weight: 500;
}

nav a:hover { color: #fff; }

main {
  max-width: 1100px;
  margin: 2rem auto;
  padding: 0 1.5rem;
}

h1 { font-size: 1.5rem; margin-bottom: 1rem; }
h2 { font-size: 1.2rem; margin: 1.5rem 0 0.5rem; }

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

th, td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #e0e0e0;
}

tr:nth-child(even) { background: #f9f9f9; }
tr:hover { background: #f0f4ff; }

.badge {
  display: inline-block;
  padding: 0.2em 0.6em;
  border-radius: 3px;
  font-size: 0.8em;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-completed          { background: #d4edda; color: #155724; }
.badge-running            { background: #fff3cd; color: #856404; }
.badge-failed             { background: #f8d7da; color: #721c24; }
.badge-pending            { background: #e2e3e5; color: #383d41; }
.badge-awaiting_approval  { background: #cce5ff; color: #004085; }

details { margin: 1rem 0; }
summary { cursor: pointer; font-weight: 600; padding: 0.5rem 0; }
details[open] summary { margin-bottom: 0.5rem; }

form div { margin-bottom: 1rem; }
label { display: block; font-weight: 500; margin-bottom: 0.25rem; }
input, select, textarea {
  width: 100%;
  padding: 0.4rem 0.6rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.95rem;
}
textarea { resize: vertical; }
input[type="checkbox"] { width: auto; }

button[type="submit"] {
  background: #1a1a2e;
  color: #fff;
  border: none;
  padding: 0.5rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}
button[type="submit"]:hover { background: #2d2d52; }

a { color: #1a1a2e; }
a:hover { color: #2d2d52; }

@media (max-width: 640px) {
  table, thead, tbody, th, td, tr { display: block; }
  thead tr { display: none; }
  td { padding-left: 40%; position: relative; }
}
```

- [ ] **Step 2: Run full test suite**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: add dashboard CSS styles"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `dashboard.py` — FastAPI app, all routes | Tasks 4–7 |
| `dashboard_store.py` — list_all_jobs, load_performance_all | Task 2 |
| 5 Jinja2 HTML templates + `_jobs_partial.html` fragment | Task 3 |
| `static/style.css` — minimal CSS | Task 8 |
| HTTP Basic Auth on all routes | Task 4 |
| HTMX auto-poll while any job RUNNING | Task 3 (`_jobs_partial.html`) |
| Background subprocess trigger (non-blocking) | Task 7 |
| `DASHBOARD_USER`/`DASHBOARD_PASSWORD` at import time → RuntimeError | Task 4 |
| `secrets.compare_digest` constant-time comparison | Task 4 |
| `GET /` jobs list, `GET /jobs/partial` fragment | Task 4 |
| `GET /jobs/{job_id}` detail with collapsible sections | Task 5 |
| `GET /metrics` performance table | Task 6 |
| `GET /trigger` form with project dropdown + confirm dialog | Task 7 |
| `POST /trigger` validation + Popen + redirect 303 | Task 7 |
| `static/htmx.min.js` vendored | Task 1 |
| `.env.example` additions | Task 1 |
| `CLAUDE.md` run commands | Task 1 |
| FastAPI dependencies in `requirements.txt` | Task 1 |
| All 12 specified tests | Tasks 4–7 |

**All requirements covered. No placeholders. Type signatures consistent across all tasks.**
