from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("logs")


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _daily_log_path(dt: datetime | None = None) -> Path:
    now = dt or datetime.now(timezone.utc)
    return LOG_DIR / f"activity-{now.strftime('%Y-%m-%d')}.log"


def _format_details(details: dict | None) -> str:
    if not details:
        return ""
    return " ".join(
        f"{key}={json.dumps(value, ensure_ascii=False)}"
        for key, value in details.items()
    )


def _write_line(line: str) -> None:
    _ensure_log_dir()
    path = _daily_log_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def log_command(command: str, details: dict | None = None) -> None:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    payload = _format_details(details)
    line = f"{timestamp} | COMMAND | {command}"
    if payload:
        line += f" | {payload}"
    _write_line(line)


def log_action(action: str, details: dict | None = None) -> None:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    payload = _format_details(details)
    line = f"{timestamp} | ACTION | {action}"
    if payload:
        line += f" | {payload}"
    _write_line(line)
