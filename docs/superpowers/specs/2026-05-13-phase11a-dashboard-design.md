# Phase 11a: Web Dashboard — Design Spec

**Date:** 2026-05-13
**Phase:** 11a
**Status:** Approved

---

## Goal

A read-only + trigger web dashboard that replaces SSH/terminal access for day-to-day pipeline operations. View job history, job outputs, performance metrics, and trigger new runs — all from a browser.

---

## Scope

- `dashboard.py` — FastAPI app, all routes
- `dashboard_store.py` — two helper functions not in `job_store.py`
- `templates/` — 5 Jinja2 HTML templates
- `static/style.css` — minimal CSS, no framework, no build step
- HTTP Basic Auth on all routes
- HTMX auto-poll on jobs list while any job is `RUNNING`
- Background subprocess trigger (non-blocking)
- Phase 11b (live checkpoint approval) is explicitly out of scope

---

## File Structure

```
dashboard.py
dashboard_store.py
templates/
  base.html
  jobs.html
  job_detail.html
  metrics.html
  trigger.html
static/
  style.css
  htmx.min.js
tests/
  test_dashboard.py
```

---

## `dashboard_store.py`

Two functions not provided by `job_store.py`:

```python
def list_all_jobs(root: Path) -> list[ContentJob]:
    """Scan output/<page>/<job_id>/job.json for all pages.
    Returns all jobs sorted newest first (by job.id, which is YYYYMMDD_HHMMSS)."""

def load_performance_all(root: Path) -> dict[str, dict[str, PlatformStats]]:
    """Reuses reporter.collect_week_data(root, date.today()).
    Returns {page_name: {platform: PlatformStats}} for the last 7 days."""
```

---

## `dashboard.py`

### Startup

Reads `DASHBOARD_USER` and `DASHBOARD_PASSWORD` from `os.environ` at import time. Raises `RuntimeError` if either is missing — dashboard refuses to start. `_ROOT = Path(__file__).resolve().parent`.

### Auth

FastAPI `HTTPBasic` dependency applied to all routes via `Depends(verify_auth)`. Uses `secrets.compare_digest` for constant-time comparison.

```python
def verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    correct_user = secrets.compare_digest(credentials.username, DASHBOARD_USER)
    correct_pass = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    return credentials.username
```

### Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Jobs list |
| `GET` | `/jobs/partial` | Jobs list HTML fragment (HTMX target) |
| `GET` | `/jobs/{job_id}` | Job detail |
| `GET` | `/metrics` | Performance table |
| `GET` | `/trigger` | Trigger form |
| `POST` | `/trigger` | Spawn pipeline, redirect to `/` |
| `GET` | `/static/{path}` | Static files |

### CLI

```python
if __name__ == "__main__":
    import uvicorn, argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("dashboard:app", host=args.host, port=args.port, reload=False)
```

---

## Pages

### `GET /` — Jobs list

Renders `jobs.html`. Calls `list_all_jobs(root)`, passes to template.

Table columns: Date, Project, Brief (max 60 chars, truncated with `…`), Content Type, Status (badge), Stage.

Status badges: `COMPLETED` → green, `RUNNING` → yellow, `FAILED` → red, `PENDING` → grey.

If `output/` doesn't exist or no jobs found: renders "No jobs yet." message.

**HTMX auto-poll:** if any job has `status=RUNNING`, the `<tbody>` element has:
```html
hx-get="/jobs/partial"
hx-trigger="every 10s"
hx-swap="outerHTML"
```
This replaces itself every 10 seconds. When no running jobs remain, the replacement HTML has no `hx-trigger`, so polling stops.

`GET /jobs/partial` returns the same `<tbody>` fragment — same logic as `/`, just renders the table body only.

### `GET /jobs/{job_id}` — Job detail

Calls `find_job(job_id)` from `job_store.py`. Returns 404 if not found.

Renders `job_detail.html` with collapsible `<details>` sections:

| Section | Source field |
|---|---|
| Brief + metadata | `job.brief`, `job.platforms`, `job.content_type`, `job.status`, `job.stage` |
| Script | `job.bella_output` (hook, body, CTA) |
| Caption + hashtags | `job.growth_strategy` |
| FAQ | read `output/<page>/<job_id>/faq.md` if exists |
| Visual prompt | `job.visual_prompt` |
| Checkpoint log | `job.checkpoint_log` |
| Publish result | `job.publish_result` |

Sections with no data are hidden (not rendered).

### `GET /metrics` — Performance

Calls `load_performance_all(root)`. Renders `metrics.html`.

One table per brand page. Columns: Platform, Jobs, Reach, Likes, Saves, Shares, Top Post.

Numbers formatted with comma separators. If no data: "No performance data for the last 7 days."

### `GET /trigger` — Trigger form

Renders `trigger.html`. Project dropdown populated from `sorted(root.glob("projects/*/pm_profile.yaml"))` — shows available project slugs. Content type dropdown: `video`, `article`, `image`, `infographic`. Brief textarea. Dry Run checkbox (checked by default in development).

Form has `onsubmit="return confirm('Start this pipeline run?')"` — browser confirmation dialog before submit. Prevents accidental runs.

### `POST /trigger` — Spawn pipeline

Form fields: `project`, `brief`, `content_type`, `dry_run` (optional checkbox).

**Validation:** `project` must match a folder under `root/projects/`. If not: return 400 "Unknown project".

**Spawn:**
```python
cmd = [sys.executable, "main.py",
       "--project", project,
       "--brief", brief,
       "--content-type", content_type,
       "--unattended"]
if dry_run:
    cmd.append("--dry-run")
subprocess.Popen(cmd, cwd=_ROOT)
```

`subprocess.Popen` (non-blocking). Does not wait for completion.

Redirect: `RedirectResponse("/", status_code=303)`.

---

## Templates

### `base.html`

Shared layout. Nav links: Jobs, Metrics, New Run. Loads HTMX from `static/htmx.min.js` (vendored — no CDN dependency). Links `static/style.css`.

### `jobs.html`, `job_detail.html`, `metrics.html`, `trigger.html`

Extend `base.html`. Render data passed from routes.

---

## `static/style.css`

Minimal CSS only:
- Clean sans-serif font, white background, max-width container
- Status badge colors (green/yellow/red/grey)
- Table styling (striped rows, hover)
- `<details>` section styling
- Responsive: stacks on narrow screens

No CSS framework. No JavaScript except HTMX (loaded from CDN).

---

## Authentication Notes

- `DASHBOARD_USER` and `DASHBOARD_PASSWORD` read at startup
- Missing either → `RuntimeError` at startup (not at first request)
- Credentials verified on every request
- No session cookies — stateless HTTP Basic on every call

---

## Environment

`.env.example` gains:
```
DASHBOARD_USER=
DASHBOARD_PASSWORD=
```

`CLAUDE.md` gains:
```bash
# Run dashboard
python dashboard.py

# Dashboard on VPS (accessible from outside)
python dashboard.py --host 0.0.0.0 --port 8000
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing `DASHBOARD_USER` or `DASHBOARD_PASSWORD` | `RuntimeError` at startup |
| Wrong credentials | 401 + WWW-Authenticate header |
| Unknown `job_id` | 404 page |
| `output/` missing | Jobs list shows "No jobs yet." |
| Metrics with no data | Shows "No performance data." |
| Unknown project in trigger | 400 response |
| `faq.md` missing for job | FAQ section not rendered |

---

## Testing

`tests/test_dashboard.py` using FastAPI `TestClient`:

- `test_dashboard_requires_auth` — GET `/` without credentials → 401
- `test_dashboard_wrong_credentials` — wrong password → 401
- `test_jobs_list_empty` — no output dir, authenticated → 200, "No jobs"
- `test_jobs_list_shows_job` — write a job.json, verify brief appears in response
- `test_jobs_partial_returns_fragment` — GET `/jobs/partial` returns HTML without full page
- `test_job_detail_404` — unknown job_id → 404
- `test_job_detail_shows_brief` — real job → 200, brief in response
- `test_metrics_no_data` — no output → 200, "No performance data"
- `test_trigger_get_shows_form` — GET `/trigger` → 200, form present
- `test_trigger_spawns_subprocess` — mock `subprocess.Popen`, POST valid form → Popen called with correct args, redirect 303
- `test_trigger_rejects_unknown_project` — project not in `projects/` → 400
- `test_dashboard_refuses_start_without_env` — monkeypatch away env vars → RuntimeError

---

## Dependencies to Add to `requirements.txt`

```
fastapi
uvicorn[standard]
jinja2
python-multipart
```

(HTMX loaded from CDN — no npm needed)

---

## Out of Scope

- Live checkpoint approval (Phase 11b)
- Job cancellation
- Log streaming
- User accounts / roles
- HTTPS termination (handled by nginx/reverse proxy on VPS)
- Mobile-specific design (responsive enough, not optimised)
