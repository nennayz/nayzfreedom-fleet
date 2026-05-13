"""notifier.py — sends Slack alerts for failed scheduler jobs."""
from __future__ import annotations

import os
import sys

import requests


def send_slack_alert(
    failures: list[dict],
    run_date: str,
    total: int,
    dry_run: bool = False,
) -> None:
    """Send a Slack alert summarising failed pipeline jobs.

    Args:
        failures: List of failure dicts with keys: project, brief, content_type,
                  exit_code (int or None for timeout).
        run_date: Human-readable date string for the run (e.g. "2026-05-13").
        total:    Total number of jobs attempted in the run.
        dry_run:  If True, print the message to stdout instead of posting.
    """
    n = len(failures)
    lines = [f":rotating_light: NayzFreedom Scheduler — {n}/{total} jobs failed ({run_date})", ""]
    for f in failures:
        label = "timeout" if f["exit_code"] is None else f"exit {f['exit_code']}"
        lines.append(f"• {f['project']} | {f['brief']} | {f['content_type']} → {label}")

    message = "\n".join(lines)

    if dry_run:
        print(message)
        return

    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("WARNING: SLACK_WEBHOOK_URL not set — skipping Slack alert.", file=sys.stderr)
        return

    try:
        with requests.post(url, json={"text": message}, timeout=10) as resp:
            if not (200 <= resp.status_code < 300):
                print(
                    f"WARNING: Slack webhook returned status {resp.status_code}.",
                    file=sys.stderr,
                )
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Failed to send Slack alert: {exc}", file=sys.stderr)
