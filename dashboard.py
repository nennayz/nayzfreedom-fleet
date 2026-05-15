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
from dashboard_store import list_all_jobs, load_performance_all, summarize_jobs
from job_store import find_job
from project_loader import load_project

DASHBOARD_USER = os.environ.get("DASHBOARD_USER")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
if not DASHBOARD_USER or not DASHBOARD_PASSWORD:
    raise RuntimeError(
        "DASHBOARD_USER and DASHBOARD_PASSWORD must be set in environment before starting the dashboard."
    )

_ROOT = Path(__file__).resolve().parent

VALID_CONTENT_TYPES = {"video", "article", "image", "infographic"}
MAX_BRIEF_LEN = 2000

CREW = [
    {"slug": "robin", "name": "Robin", "image": "/static/crew/robin.png", "ship_role": "Chief Officer", "operational_role": "Orchestrator", "summary": "Keeps The Aurora aligned and turns briefs into action.", "personality": "calm, strategic, decisive", "strengths": ["coordination", "prioritization", "decision framing"], "watch_outs": ["can optimize for throughput before artistry"], "inputs": ["captain brief", "project context", "performance history"], "outputs": ["mission route", "crew dispatch", "final coordination"], "quote": "A good voyage is won before the sails rise."},
    {"slug": "mia", "name": "Mia Trend", "image": "/static/crew/mia.png", "ship_role": "Lookout", "operational_role": "Trend Researcher", "summary": "Scans the horizon for trends, signals, and timely opportunities.", "personality": "curious, alert, analytical", "strengths": ["trend sensing", "research", "signal detection"], "watch_outs": ["fresh signals still need strategic judgment"], "inputs": ["brief", "platforms"], "outputs": ["trend data", "formats", "timely context"], "quote": "The horizon always speaks first."},
    {"slug": "zoe", "name": "Zoe Spark", "image": "/static/crew/zoe.png", "ship_role": "Cartographer of Ideas", "operational_role": "Idea Generator", "summary": "Turns research into creative routes worth pursuing.", "personality": "bright, imaginative, energetic", "strengths": ["ideation", "hooks", "angles"], "watch_outs": ["many routes still require one sharp choice"], "inputs": ["trend data", "brand context"], "outputs": ["idea set", "hooks", "content angles"], "quote": "One spark is enough to chart a new sea."},
    {"slug": "bella", "name": "Bella Quill", "image": "/static/crew/bella.png", "ship_role": "Scribe", "operational_role": "Script Writer", "summary": "Shapes the chosen idea into words that sound like the brand.", "personality": "elegant, persuasive, empathetic", "strengths": ["voice", "structure", "copy"], "watch_outs": ["needs a strong idea to sing"], "inputs": ["selected idea", "brand voice"], "outputs": ["script", "article", "caption copy"], "quote": "Every voyage needs a tale worth repeating."},
    {"slug": "lila", "name": "Lila Lens", "image": "/static/crew/lila.png", "ship_role": "Visual Director", "operational_role": "Visual Creator", "summary": "Translates story into imagery, mood, and cinematic direction.", "personality": "stylish, visionary, polished", "strengths": ["composition", "visual language", "prompt direction"], "watch_outs": ["visual ambition must still serve the brief"], "inputs": ["script", "content type", "brand aesthetic"], "outputs": ["visual prompt", "image/video direction"], "quote": "If the eye believes it, the heart follows."},
    {"slug": "nora", "name": "Nora Sharp", "image": "/static/crew/nora.png", "ship_role": "Inspector", "operational_role": "QA Editor", "summary": "Protects standards before anything leaves the ship.", "personality": "precise, honest, supportive", "strengths": ["review", "quality control", "risk spotting"], "watch_outs": ["perfection must not stall momentum"], "inputs": ["script", "visuals"], "outputs": ["QA verdict", "revision feedback"], "quote": "Better one hard truth on deck than one weak post at sea."},
    {"slug": "roxy", "name": "Roxy Rise", "image": "/static/crew/roxy.png", "ship_role": "Trade Winds Strategist", "operational_role": "Growth Strategist", "summary": "Finds the best timing, framing, and route to reach the audience.", "personality": "upbeat, data-driven, tactical", "strengths": ["distribution", "hashtags", "timing"], "watch_outs": ["growth should amplify, not distort, the message"], "inputs": ["finished content", "platform context"], "outputs": ["caption", "hashtags", "posting timing"], "quote": "Even treasure needs the right tide."},
    {"slug": "emma", "name": "Emma Heart", "image": "/static/crew/emma.png", "ship_role": "Community Keeper", "operational_role": "Community Specialist", "summary": "Prepares warm, useful responses for the people waiting on shore.", "personality": "warm, clear, attentive", "strengths": ["community care", "FAQ", "tone"], "watch_outs": ["kindness works best with clarity"], "inputs": ["final content", "brand context"], "outputs": ["FAQ", "response guidance"], "quote": "A crew is remembered by how it welcomes people aboard."},
]

VOYAGE_STAGES = [
    ("mia_done", "Scout the Horizon", "Mia Trend"),
    ("zoe_done", "Chart the Route", "Zoe Spark"),
    ("bella_done", "Write the Tale", "Bella Quill"),
    ("lila_done", "Shape the Vision", "Lila Lens"),
    ("nora_done", "Inspect the Cargo", "Nora Sharp"),
    ("roxy_done", "Set the Trade Winds", "Roxy Rise"),
    ("emma_done", "Prepare the Port Talk", "Emma Heart"),
    ("publish_done", "Raise the Flag", "Publish"),
]

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


def _stage_completed(job, stage: str) -> bool:
    order = [item[0] for item in VOYAGE_STAGES]
    return job.stage in order and order.index(job.stage) >= order.index(stage)


@app.get("/", response_class=HTMLResponse)
def captains_deck(request: Request, _: str = Depends(verify_auth)):
    jobs = list_all_jobs(_root(request))
    performance = load_performance_all(_root(request))
    return templates.TemplateResponse(
        request,
        "captains_deck.html",
        {
            "jobs": jobs[:5],
            "summary": summarize_jobs(jobs),
            "performance": performance,
        },
    )


@app.get("/aurora", response_class=HTMLResponse)
def aurora_overview(request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    jobs = list_all_jobs(root)
    projects = sorted(p.parent.name for p in root.glob("projects/*/pm_profile.yaml"))
    performance = load_performance_all(root)
    return templates.TemplateResponse(
        request,
        "aurora.html",
        {
            "jobs": jobs[:5],
            "summary": summarize_jobs(jobs),
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
    member = next((member for member in CREW if member["slug"] == slug), None)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Crew member {slug!r} not found")
    return templates.TemplateResponse(request, "crew_detail.html", {"member": member})


@app.get("/aurora/islands/{project_slug}", response_class=HTMLResponse)
def island_detail(project_slug: str, request: Request, _: str = Depends(verify_auth)):
    try:
        pm = load_project(project_slug)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Island {project_slug!r} not found")
    jobs = [job for job in list_all_jobs(_root(request)) if job.project == project_slug]
    return templates.TemplateResponse(
        request,
        "island_detail.html",
        {"project_slug": project_slug, "pm": pm, "jobs": jobs[:5]},
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
    projects = sorted(p.parent.name for p in root.glob("projects/*/pm_profile.yaml"))
    return templates.TemplateResponse(request, "trigger.html", {"projects": projects})


@app.get("/freedom", response_class=HTMLResponse)
def freedom_overview(request: Request, _: str = Depends(verify_auth)):
    return templates.TemplateResponse(request, "freedom.html", {})


@app.get("/lyra", response_class=HTMLResponse)
def lyra_overview(request: Request, _: str = Depends(verify_auth)):
    return templates.TemplateResponse(request, "lyra.html", {})


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
    completed_stages = {stage for stage, _, _ in VOYAGE_STAGES if _stage_completed(job, stage)}
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "job": job,
            "faq_content": faq_content,
            "voyage_stages": VOYAGE_STAGES,
            "completed_stages": completed_stages,
            "progress_count": len(completed_stages),
            "total_stages": len(VOYAGE_STAGES),
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
    valid = {p.parent.name for p in root.glob("projects/*/pm_profile.yaml")}
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
