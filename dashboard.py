from __future__ import annotations
import os
import secrets
import subprocess
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dashboard_store import list_all_jobs, load_performance_all
from job_store import find_job

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
    jobs = list_all_jobs(_root(request))
    return templates.TemplateResponse(request, "jobs.html", {"jobs": jobs})


@app.get("/jobs/partial", response_class=HTMLResponse)
def jobs_partial(request: Request, _: str = Depends(verify_auth)):
    jobs = list_all_jobs(_root(request))
    return templates.TemplateResponse(request, "_jobs_partial.html", {"jobs": jobs})


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
        request, "job_detail.html", {"job": job, "faq_content": faq_content}
    )


@app.get("/metrics", response_class=HTMLResponse)
def metrics(request: Request, _: str = Depends(verify_auth)):
    data = load_performance_all(_root(request))
    return templates.TemplateResponse(request, "metrics.html", {"data": data})


@app.get("/trigger", response_class=HTMLResponse)
def trigger_form(request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    projects = sorted(p.parent.name for p in root.glob("projects/*/pm_profile.yaml"))
    return templates.TemplateResponse(request, "trigger.html", {"projects": projects})


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


if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("dashboard:app", host=args.host, port=args.port, reload=False)
