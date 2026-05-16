from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import requests
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
from job_store import find_job, save_job
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
OPS_PUBLIC_BASE_URL = os.environ.get("OPS_PUBLIC_BASE_URL", "https://fleet.nayzfreedom.cloud").rstrip("/")
OPS_UNITS = [
    "nayzfreedom-dashboard.service",
    "nayzfreedom-bot.service",
    "nayzfreedom-scheduler.timer",
    "nayzfreedom-reporter.timer",
    "nayzfreedom-instagram-queue.timer",
    "nayzfreedom-backup.timer",
    "nayzfreedom-healthcheck.timer",
    "nayzfreedom-production-summary.timer",
]
OPS_ACTIONS = {
    "backup": {
        "label": "Run backup now",
        "unit": "nayzfreedom-backup.service",
        "verb": "start",
    },
    "instagram_queue": {
        "label": "Run Instagram queue now",
        "unit": "nayzfreedom-instagram-queue.service",
        "verb": "start",
    },
    "production_summary": {
        "label": "Run production summary now",
        "unit": "nayzfreedom-production-summary.service",
        "verb": "start",
    },
    "restart_dashboard": {
        "label": "Restart dashboard",
        "unit": "nayzfreedom-dashboard.service",
        "verb": "restart",
        "delayed": True,
    },
}

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(_ROOT / "templates"))
security = HTTPBasic()


def _status_label(value: object) -> str:
    raw = getattr(value, "value", str(value))
    return raw.replace("_", " ").title()


templates.env.filters["status_label"] = _status_label


def _publish_status_items(job) -> list[dict[str, str]]:
    result = job.publish_result or {}
    if not isinstance(result, dict):
        return []
    items = []
    for platform in ("facebook", "instagram", "tiktok", "youtube"):
        value = result.get(platform)
        if not isinstance(value, dict):
            continue
        status = value.get("status", "unknown")
        if platform == "facebook" and status == "scheduled":
            label = "Facebook scheduled"
        elif platform == "instagram" and status == "published":
            label = "Instagram published"
        elif platform == "instagram" and status == "pending_queue":
            label = "Instagram pending queue"
        else:
            label = f"{platform.title()} {str(status).replace('_', ' ')}"
        items.append({"platform": platform, "status": str(status), "label": label})
    return items


templates.env.globals["publish_status_items"] = _publish_status_items


def _publish_history_items(job) -> list[dict[str, str]]:
    items = []
    for item in _publish_status_items(job):
        value = (job.publish_result or {}).get(item["platform"], {})
        if not isinstance(value, dict):
            continue
        detail = value.get("due_at") or value.get("id") or value.get("reason") or value.get("error") or ""
        items.append({**item, "detail": str(detail)})
    return items


templates.env.globals["publish_history_items"] = _publish_history_items


def _filter_jobs(jobs, selected: str):
    if selected == "running":
        return [job for job in jobs if getattr(job.status, "value", str(job.status)) == "running"]
    if selected == "failed":
        return [job for job in jobs if getattr(job.status, "value", str(job.status)) == "failed"]
    if selected in {"scheduled", "queued", "published"}:
        target = {"scheduled": "scheduled", "queued": "pending_queue", "published": "published"}[selected]
        return [
            job for job in jobs
            if any(item["status"] == target for item in _publish_status_items(job))
        ]
    return jobs


def _mission_filters(jobs, selected: str) -> list[dict[str, object]]:
    filters = [
        ("all", "All"),
        ("running", "Running"),
        ("failed", "Failed"),
        ("scheduled", "Scheduled"),
        ("queued", "Queued"),
        ("published", "Published"),
    ]
    return [
        {
            "key": key,
            "label": label,
            "active": key == selected,
            "count": len(_filter_jobs(jobs, key)),
        }
        for key, label in filters
    ]


def _run_command(args: list[str], timeout: int = 8) -> dict[str, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {"state": "unavailable", "detail": f"{args[0]} is not installed here."}
    except subprocess.TimeoutExpired:
        return {"state": "failed", "detail": f"{args[0]} timed out."}
    output = (result.stdout or result.stderr or "").strip()
    return {
        "state": "ok" if result.returncode == 0 else "failed",
        "detail": output[:500] if output else f"exit={result.returncode}",
    }


def _systemctl_args(verb: str, unit: str) -> list[str]:
    return ["sudo", "-n", "systemctl", verb, unit]


def _ops_action_buttons() -> list[dict[str, str]]:
    return [
        {"key": key, "label": str(config["label"])}
        for key, config in OPS_ACTIONS.items()
    ]


def _run_ops_action(action: str) -> dict[str, str]:
    config = OPS_ACTIONS.get(action)
    if config is None:
        return {"name": action, "state": "Failed", "detail": "Unknown Ops action."}

    label = str(config["label"])
    unit = str(config["unit"])
    verb = str(config["verb"])

    if config.get("delayed"):
        code = (
            "import subprocess,time;"
            "time.sleep(1);"
            f"subprocess.run({json.dumps(_systemctl_args(verb, unit))})"
        )
        try:
            subprocess.Popen([sys.executable, "-c", code], cwd=str(_ROOT))
        except Exception as exc:  # noqa: BLE001
            return {"name": label, "state": "Failed", "detail": str(exc)[:300]}
        return {"name": label, "state": "Ready", "detail": f"Queued {verb} for {unit}."}

    result = _run_command(_systemctl_args(verb, unit), timeout=30)
    state = "Ready" if result["state"] == "ok" else "Failed"
    detail = result["detail"]
    if result["state"] == "failed" and "password" in detail.lower():
        detail = "sudo permission missing for this Ops action."
    return {"name": label, "state": state, "detail": detail}


def _ops_unit_status() -> list[dict[str, str]]:
    rows = []
    for unit in OPS_UNITS:
        result = _run_command(["systemctl", "is-active", unit], timeout=4)
        active = result["state"] == "ok" and result["detail"] == "active"
        rows.append({
            "name": unit,
            "state": "Ready" if active else "Missing" if result["state"] == "unavailable" else "Failed",
            "detail": result["detail"],
        })
    return rows


def _latest_backup_status() -> dict[str, str]:
    backup_root = Path(os.environ.get("BACKUP_ROOT", "/opt/nayzfreedom-backups"))
    if not backup_root.exists():
        return {"state": "Missing", "detail": f"{backup_root} not found"}
    try:
        backups = sorted([path for path in backup_root.iterdir() if path.is_dir()], reverse=True)
    except PermissionError:
        return {"state": "Failed", "detail": f"Permission denied: {backup_root}"}
    if not backups:
        return {"state": "Missing", "detail": "No backup folders found."}
    latest = backups[0]
    archive = latest / "state.tgz"
    checksum = latest / "state.tgz.sha256"
    if archive.exists() and checksum.exists():
        size_mb = archive.stat().st_size / (1024 * 1024)
        return {"state": "Ready", "detail": f"{latest.name} - {size_mb:.1f} MB"}
    return {"state": "Failed", "detail": f"{latest.name} is missing archive or checksum."}


def _ops_publish_errors(jobs, limit: int = 6) -> list[dict[str, str]]:
    rows = []
    for job in jobs:
        for platform, value in (job.publish_result or {}).items():
            if not isinstance(value, dict) or value.get("status") != "failed":
                continue
            error = str(value.get("error") or value.get("reason") or "failed")
            meta_token = os.environ.get("META_ACCESS_TOKEN", "")
            if meta_token:
                error = error.replace(meta_token, "<redacted>")
            rows.append({
                "job_id": job.id,
                "platform": str(platform),
                "detail": error[:220],
            })
    return rows[:limit]


def _signed_request_for_smoke() -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"user_id": "ops-smoke"}).encode()).decode().rstrip("=")
    app_secret = os.environ.get("META_APP_SECRET", "")
    if not app_secret:
        return f"unused.{payload}"
    sig = hmac.new(app_secret.encode("utf-8"), msg=payload.encode("utf-8"), digestmod=hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{encoded_sig}.{payload}"


def _http_smoke(name: str, method: str, url: str, **kwargs) -> dict[str, str]:
    try:
        response = requests.request(method, url, timeout=8, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "state": "Failed", "detail": str(exc)[:240]}
    ok = 200 <= response.status_code < 300
    detail = f"HTTP {response.status_code}"
    if name == "Data deletion callback" and ok:
        try:
            detail = f"confirmation={response.json().get('confirmation_code', 'missing')}"
        except ValueError:
            detail = "JSON parse failed"
            ok = False
    return {"name": name, "state": "Ready" if ok else "Failed", "detail": detail}


def _ops_smoke_results(root: Path) -> list[dict[str, str]]:
    signed_request = _signed_request_for_smoke()
    results = [
        _http_smoke("Health URL", "GET", f"{OPS_PUBLIC_BASE_URL}/healthz"),
        _http_smoke("Privacy HEAD", "HEAD", f"{OPS_PUBLIC_BASE_URL}/privacy"),
        _http_smoke("Data deletion HTML", "GET", f"{OPS_PUBLIC_BASE_URL}/data_deletion.html"),
        _http_smoke(
            "Data deletion callback",
            "POST",
            f"{OPS_PUBLIC_BASE_URL}/data-deletion-callback",
            data={"signed_request": signed_request},
        ),
    ]
    restore_script = root / "deploy" / "restore_smoke.sh"
    if restore_script.exists():
        restore = _run_command([str(restore_script)], timeout=20)
        results.append({
            "name": "Backup restore smoke",
            "state": "Ready" if restore["state"] == "ok" else "Failed",
            "detail": restore["detail"],
        })
    else:
        results.append({"name": "Backup restore smoke", "state": "Missing", "detail": "restore_smoke.sh not found"})
    return results


def _ops_snapshot(root: Path, smoke_results: list[dict[str, str]] | None = None) -> dict[str, object]:
    jobs = list_all_jobs(root)
    summary = summarize_jobs(jobs)
    return {
        "units": _ops_unit_status(),
        "backup": _latest_backup_status(),
        "summary": summary,
        "latest_jobs": jobs[:5],
        "publish_errors": _ops_publish_errors(jobs),
        "smoke_results": smoke_results,
        "action_buttons": _ops_action_buttons(),
        "action_result": None,
    }


@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok", "service": "nayzfreedom-dashboard"})


@app.api_route("/privacy", methods=["GET", "HEAD"], response_class=HTMLResponse)
def privacy_policy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@app.api_route("/data-deletion", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/data_deletion.html", methods=["GET", "HEAD"], response_class=HTMLResponse)
def data_deletion(request: Request):
    return templates.TemplateResponse(request, "data_deletion.html", {})


def _decode_meta_signed_request(signed_request: str) -> dict:
    if "." not in signed_request:
        raise ValueError("signed_request must contain a signature and payload")

    encoded_sig, encoded_payload = signed_request.split(".", 1)
    app_secret = os.environ.get("META_APP_SECRET", "")
    if app_secret:
        expected_sig = hmac.new(
            app_secret.encode("utf-8"),
            msg=encoded_payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        actual_sig = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        if not hmac.compare_digest(actual_sig, expected_sig):
            raise ValueError("signed_request signature mismatch")

    payload = base64.urlsafe_b64decode(
        encoded_payload + "=" * (-len(encoded_payload) % 4)
    )
    return json.loads(payload.decode("utf-8"))


@app.post("/data-deletion-callback")
async def data_deletion_callback(signed_request: str = Form(...)):
    try:
        payload = _decode_meta_signed_request(signed_request)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_id = str(payload.get("user_id") or payload.get("user", {}).get("id") or "unknown")
    confirmation_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
    confirmation_code = f"slayhack-delete-{confirmation_hash}"
    return JSONResponse(
        {
            "url": "https://fleet.nayzfreedom.cloud/data-deletion",
            "confirmation_code": confirmation_code,
        }
    )


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
    selected_filter = request.query_params.get("filter", "all")
    if selected_filter not in {"all", "running", "failed", "scheduled", "queued", "published"}:
        selected_filter = "all"
    filtered_jobs = _filter_jobs(jobs, selected_filter)
    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "jobs": filtered_jobs,
            "mission_filters": _mission_filters(jobs, selected_filter),
            "selected_filter": selected_filter,
        },
    )


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


@app.get("/ops", response_class=HTMLResponse)
def ops_dashboard(request: Request, _: str = Depends(verify_auth)):
    snapshot = _ops_snapshot(_root(request))
    return templates.TemplateResponse(request, "ops.html", snapshot)


@app.post("/ops/smoke-test", response_class=HTMLResponse)
def ops_smoke_test(request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    snapshot = _ops_snapshot(root, smoke_results=_ops_smoke_results(root))
    return templates.TemplateResponse(request, "ops.html", snapshot)


@app.post("/ops/actions/{action}", response_class=HTMLResponse)
def ops_action(action: str, request: Request, _: str = Depends(verify_auth)):
    root = _root(request)
    action_result = _run_ops_action(action)
    snapshot = _ops_snapshot(root)
    snapshot["action_result"] = action_result
    return templates.TemplateResponse(request, "ops.html", snapshot)


@app.get("/jobs", response_class=HTMLResponse)
def jobs_redirect(_: str = Depends(verify_auth)):
    return RedirectResponse("/aurora/missions", status_code=307)


@app.get("/jobs/partial", response_class=HTMLResponse)
def jobs_partial(request: Request, _: str = Depends(verify_auth)):
    jobs = list_all_jobs(_root(request))
    selected_filter = request.query_params.get("filter", "all")
    if selected_filter not in {"all", "running", "failed", "scheduled", "queued", "published"}:
        selected_filter = "all"
    return templates.TemplateResponse(
        request,
        "_jobs_partial.html",
        {"jobs": _filter_jobs(jobs, selected_filter), "selected_filter": selected_filter},
    )


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


@app.post("/jobs/{job_id}/retry-publish")
def retry_publish(job_id: str, _: str = Depends(verify_auth)):
    try:
        find_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    subprocess.Popen(
        [sys.executable, "main.py", "--publish-only", job_id, "--schedule"],
        cwd=str(_ROOT),
    )
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/publish-instagram-now")
def publish_instagram_now(job_id: str, _: str = Depends(verify_auth)):
    from datetime import datetime, timezone
    import time

    try:
        job = find_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    ig_result = (job.publish_result or {}).get("instagram", {})
    if not isinstance(ig_result, dict) or ig_result.get("status") != "pending_queue":
        raise HTTPException(status_code=400, detail="Instagram is not pending queue for this job")
    ig_result["scheduled_publish_time"] = int(time.time()) - 1
    ig_result["due_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ig_result["publish_now_requested"] = True
    save_job(job)
    subprocess.Popen([sys.executable, "instagram_queue.py"], cwd=str(_ROOT))
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


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
