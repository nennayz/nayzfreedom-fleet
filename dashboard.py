from __future__ import annotations
import os
import secrets
import subprocess
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from crew_registry import CREW, WORKFLOW_STEPS, get_crew_member
from dashboard_store import (
    active_jobs,
    attention_jobs,
    command_brief,
    fleet_status,
    list_all_jobs,
    load_performance_all,
    summarize_jobs,
)
from job_store import find_job
from project_loader import (
    list_project_slugs,
    load_project,
    load_project_page_name,
    project_slug_matches,
    resolve_project_slug,
)

DASHBOARD_USER = os.environ.get("DASHBOARD_USER")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
if not DASHBOARD_USER or not DASHBOARD_PASSWORD:
    raise RuntimeError(
        "DASHBOARD_USER and DASHBOARD_PASSWORD must be set in environment before starting the dashboard."
    )

_ROOT = Path(__file__).resolve().parent

VALID_CONTENT_TYPES = {"video", "article", "image", "infographic"}
MAX_BRIEF_LEN = 2000

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(_ROOT / "templates"))
security = HTTPBasic()


def _status_label(value: object) -> str:
    raw = getattr(value, "value", str(value))
    return raw.replace("_", " ").title()


templates.env.filters["status_label"] = _status_label


@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok", "service": "nayzfreedom-dashboard"})


@app.api_route("/privacy", methods=["GET", "HEAD"], response_class=HTMLResponse)
def privacy_policy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@app.api_route("/data-deletion", methods=["GET", "HEAD"], response_class=HTMLResponse)
def data_deletion(request: Request):
    return templates.TemplateResponse(request, "data_deletion.html", {})


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    correct_user = secrets.compare_digest(credentials.username, DASHBOARD_USER)
    correct_pass = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def _root(request: Request) -> Path:
    return getattr(request.app.state, "root", _ROOT)


def _project_options(root: Path) -> list[dict]:
    options = []
    for slug in list_project_slugs(root):
        options.append({"slug": slug, "label": load_project_page_name(slug, root=root)})
    return options


def _build_voyage_steps(job) -> list[dict]:
    order = [step.stage for step in WORKFLOW_STEPS]
    current_index = order.index(job.stage) if job.stage in order else 0
    status_value = getattr(job.status, "value", str(job.status))
    steps = []
    for index, step in enumerate(WORKFLOW_STEPS):
        member = get_crew_member(step.crew_slug) if step.crew_slug else None
        if index < current_index:
            state = "done"
        elif index == current_index:
            if status_value == "failed":
                state = "blocked"
            elif status_value == "completed" or step.stage == "publish_done":
                state = "done"
            else:
                state = "current"
        else:
            state = "upcoming"
        steps.append({"step": step, "member": member, "state": state})
    return steps


def _mission_command(job, voyage_steps: list[dict], completed_count: int) -> dict:
    status_value = getattr(job.status, "value", str(job.status))
    current = next(
        (item for item in voyage_steps if item["state"] in {"current", "blocked"}),
        voyage_steps[-1] if voyage_steps else None,
    )
    step = current["step"] if current else None
    member = current["member"] if current else None
    owner = member.name if member else step.owner_name if step else "Mission crew"

    if status_value == "failed":
        state = "Needs Captain"
        action = "Review the failure and decide whether to rerun, redirect, or close the mission."
    elif status_value == "awaiting_approval":
        state = "Needs Captain"
        action = "Approve or redirect the waiting checkpoint before the workflow continues."
    elif status_value == "completed":
        state = "Complete"
        action = "Review the publish result and record performance when results arrive."
    elif status_value == "running":
        state = "In Motion"
        action = f"{owner} is holding the current stage."
    else:
        state = "Ready"
        action = "Start or resume the mission workflow."

    return {
        "state": state,
        "action": action,
        "stage_label": step.label if step else "Not started",
        "owner": owner,
        "station": step.station if step else "Mission deck",
        "progress": f"{completed_count}/{len(voyage_steps)}",
    }


def _mission_outputs(job, faq_content: str | None) -> list[dict[str, str]]:
    content_ready = job.bella_output is not None
    visual_ready = bool(job.visual_prompt or job.image_path or job.video_path)
    content_type = getattr(job.content_type, "value", job.content_type)
    visual_required = content_type != "article"
    growth_ready = job.growth_strategy is not None
    community_ready = bool(faq_content)
    publish_ready = job.publish_result is not None

    return [
        {
            "label": "Content",
            "state": "Ready" if content_ready else "Waiting",
            "detail": "Bella output is available." if content_ready else "Waiting for written content.",
        },
        {
            "label": "Visual",
            "state": "Ready" if visual_ready else "Not needed" if not visual_required else "Waiting",
            "detail": "Visual direction is available." if visual_ready else "Article mission can skip visual direction." if not visual_required else "Waiting for visual direction.",
        },
        {
            "label": "Growth",
            "state": "Ready" if growth_ready else "Waiting",
            "detail": "Caption, hashtags, and timing are available." if growth_ready else "Waiting for Roxy's strategy.",
        },
        {
            "label": "Community",
            "state": "Ready" if community_ready else "Waiting",
            "detail": "FAQ is available." if community_ready else "Waiting for Emma's FAQ.",
        },
        {
            "label": "Publish",
            "state": "Ready" if publish_ready else "Waiting",
            "detail": "Publish result is recorded." if publish_ready else "Waiting for launch result.",
        },
    ]


def _readiness_checks(root: Path) -> list[dict[str, str]]:
    deploy_dir = root / "deploy"
    required_deploy_files = [
        "nayzfreedom-dashboard.service",
        "nayzfreedom-bot.service",
        "nayzfreedom-scheduler.service",
        "nayzfreedom-scheduler.timer",
        "nayzfreedom-reporter.service",
        "nayzfreedom-reporter.timer",
        "setup.sh",
        "update.sh",
    ]
    missing_deploy = [name for name in required_deploy_files if not (deploy_dir / name).exists()]
    projects = list_project_slugs(root)
    output_dir = root / "output"
    static_required = [
        root / "static" / "style.css",
        root / "static" / "htmx.min.js",
        root / "static" / "ships" / "aurora-hero.png",
    ]
    missing_static = [path.name for path in static_required if not path.exists()]

    return [
        {
            "label": "Dashboard auth",
            "state": "Ready" if DASHBOARD_USER and DASHBOARD_PASSWORD else "Missing",
            "detail": "Basic Auth environment variables are configured.",
        },
        {
            "label": "Project config",
            "state": "Ready" if projects else "Missing",
            "detail": f"{len(projects)} project profile{'s' if len(projects) != 1 else ''} configured.",
        },
        {
            "label": "Mission output",
            "state": "Ready" if output_dir.exists() else "Waiting",
            "detail": "Output directory exists." if output_dir.exists() else "No output directory yet; first mission will create it.",
        },
        {
            "label": "Static assets",
            "state": "Ready" if not missing_static else "Missing",
            "detail": "Dashboard CSS, HTMX, and Aurora hero assets are present." if not missing_static else f"Missing: {', '.join(missing_static)}.",
        },
        {
            "label": "Deploy files",
            "state": "Ready" if not missing_deploy else "Missing",
            "detail": "Systemd services, timers, setup, and update scripts are present." if not missing_deploy else f"Missing: {', '.join(missing_deploy)}.",
        },
        {
            "label": "Privacy boundary",
            "state": "Planned",
            "detail": "Keep The Freedom private until stronger auth and memory boundaries are implemented.",
        },
    ]


@app.get("/", response_class=HTMLResponse)
def captains_deck(request: Request, _: str = Depends(verify_auth)):
    jobs = list_all_jobs(_root(request))
    performance = load_performance_all(_root(request))
    summary = summarize_jobs(jobs)
    signals = attention_jobs(jobs)
    active = active_jobs(jobs)
    brief = command_brief(jobs)
    ships = fleet_status(jobs)
    return templates.TemplateResponse(
        request,
        "captains_deck.html",
        {
            "jobs": jobs[:5],
            "summary": summary,
            "attention_jobs": signals,
            "active_jobs": active,
            "command_brief": brief,
            "fleet_status": ships,
            "performance": performance,
        },
    )


@app.get("/aurora", response_class=HTMLResponse)
def aurora_overview(request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    jobs = list_all_jobs(root)
    projects = _project_options(root)
    performance = load_performance_all(root)
    signals = attention_jobs(jobs)
    active = active_jobs(jobs)
    return templates.TemplateResponse(
        request,
        "aurora.html",
        {
            "jobs": jobs[:5],
            "summary": summarize_jobs(jobs),
            "attention_jobs": signals,
            "active_jobs": active,
            "command_brief": command_brief(jobs),
            "projects": projects,
            "performance": performance,
            "crew": CREW[:4],
        },
    )


@app.get("/aurora/crew", response_class=HTMLResponse)
def aurora_crew(request: Request, _: str = Depends(verify_auth)):
    return templates.TemplateResponse(request, "crew.html", {"crew": CREW})


@app.get("/aurora/crew/{slug}", response_class=HTMLResponse)
def aurora_character_sheet(slug: str, request: Request, _: str = Depends(verify_auth)):
    member = get_crew_member(slug)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Crew member {slug!r} not found")
    return templates.TemplateResponse(request, "crew_detail.html", {"member": member})


@app.get("/aurora/islands/{project_slug}", response_class=HTMLResponse)
def island_detail(project_slug: str, request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    project_slug = resolve_project_slug(project_slug)
    try:
        pm = load_project(project_slug, root=root)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Island {project_slug!r} not found")
    jobs = [
        job for job in list_all_jobs(root)
        if project_slug_matches(job.project, project_slug)
    ]
    summary = summarize_jobs(jobs)
    signals = attention_jobs(jobs)
    active = active_jobs(jobs)
    return templates.TemplateResponse(
        request,
        "island_detail.html",
        {
            "project_slug": project_slug,
            "pm": pm,
            "jobs": jobs[:5],
            "summary": summary,
            "attention_jobs": signals,
            "active_jobs": active,
            "command_brief": command_brief(jobs),
            "allowed_content_types": [content_type.value for content_type in pm.brand.allowed_content_types],
        },
    )


@app.get("/aurora/missions", response_class=HTMLResponse)
def aurora_missions(request: Request, _: str = Depends(verify_auth)):
    jobs = list_all_jobs(_root(request))
    return templates.TemplateResponse(request, "jobs.html", {"jobs": jobs})


@app.get("/aurora/metrics", response_class=HTMLResponse)
def aurora_metrics(request: Request, _: str = Depends(verify_auth)):
    data = load_performance_all(_root(request))
    return templates.TemplateResponse(request, "metrics.html", {"data": data})


@app.get("/aurora/new-mission", response_class=HTMLResponse)
def aurora_new_mission(request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    project_slugs = list_project_slugs(root)
    projects = _project_options(root)
    selected_project = request.query_params.get("project")
    if selected_project:
        selected_project = resolve_project_slug(selected_project)
    if selected_project not in project_slugs:
        selected_project = project_slugs[0] if project_slugs else None
    return templates.TemplateResponse(
        request,
        "trigger.html",
        {"projects": projects, "selected_project": selected_project},
    )


@app.get("/freedom", response_class=HTMLResponse)
def freedom_overview(request: Request, _: str = Depends(verify_auth)):
    return templates.TemplateResponse(request, "freedom.html", {})


@app.get("/lyra", response_class=HTMLResponse)
def lyra_overview(request: Request, _: str = Depends(verify_auth)):
    return templates.TemplateResponse(request, "lyra.html", {})


@app.get("/readiness", response_class=HTMLResponse)
def readiness(request: Request, _: str = Depends(verify_auth)):
    checks = _readiness_checks(_root(request))
    return templates.TemplateResponse(request, "readiness.html", {"checks": checks})


@app.get("/jobs", response_class=HTMLResponse)
def jobs_redirect(_: str = Depends(verify_auth)):
    return RedirectResponse("/aurora/missions", status_code=307)


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
    voyage_steps = _build_voyage_steps(job)
    completed_count = sum(1 for item in voyage_steps if item["state"] == "done")
    mission_command = _mission_command(job, voyage_steps, completed_count)
    mission_outputs = _mission_outputs(job, faq_content)
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "job": job,
            "faq_content": faq_content,
            "voyage_steps": voyage_steps,
            "progress_count": completed_count,
            "total_stages": len(voyage_steps),
            "mission_command": mission_command,
            "mission_outputs": mission_outputs,
        },
    )


@app.get("/metrics", response_class=HTMLResponse)
def metrics_redirect(_: str = Depends(verify_auth)):
    return RedirectResponse("/aurora/metrics", status_code=307)


@app.get("/trigger", response_class=HTMLResponse)
def trigger_form_redirect(_: str = Depends(verify_auth)):
    return RedirectResponse("/aurora/new-mission", status_code=307)


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
    valid = set(list_project_slugs(root))
    project = resolve_project_slug(project)
    if project not in valid:
        raise HTTPException(status_code=400, detail="Unknown project")
    if content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid content_type")
    if len(brief) > MAX_BRIEF_LEN:
        raise HTTPException(status_code=400, detail=f"Brief too long (max {MAX_BRIEF_LEN} chars)")
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
    return RedirectResponse("/aurora/missions", status_code=303)


if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("dashboard:app", host=args.host, port=args.port, reload=False)
