# Phase 9: Failure Alerting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send a single Slack webhook message at the end of a scheduler run when one or more jobs failed.

**Architecture:** New `notifier.py` module exposes `send_slack_alert(failures, run_date, total, dry_run)`. `scheduler.py` accumulates failures during the job loop and calls `send_slack_alert` after the loop completes. `dry_run=True` prints to stdout instead of POSTing.

**Tech Stack:** Python stdlib (`os`, `datetime`), `requests` (already in requirements), `pytest`, `pytest-mock`

---

### Task 1: Create `notifier.py`

**Files:**
- Create: `notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notifier.py`:

```python
from __future__ import annotations
import os
import pytest
from unittest.mock import patch, MagicMock


FAILURES_ONE = [
    {"project": "slay_hack", "brief": "article_1", "content_type": "article", "exit_code": 1},
]
FAILURES_TIMEOUT = [
    {"project": "slay_hack", "brief": "short_video_1", "content_type": "video", "exit_code": None},
]
FAILURES_TWO = FAILURES_ONE + FAILURES_TIMEOUT


def test_send_slack_alert_dry_run_prints_message(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    from notifier import send_slack_alert
    send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=True)
    out = capsys.readouterr().out
    assert "1/7 jobs failed" in out
    assert "slay_hack" in out
    assert "article_1" in out
    assert "article" in out
    assert "exit 1" in out


def test_send_slack_alert_posts_to_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    with patch("notifier.requests.post", mock_post):
        from notifier import send_slack_alert
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)
    mock_post.assert_called_once()
    url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
    assert url == "https://hooks.slack.com/fake"
    assert "1/7 jobs failed" in kwargs["json"]["text"]
    assert "slay_hack" in kwargs["json"]["text"]


def test_send_slack_alert_missing_env_skips(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    mock_post = MagicMock()
    with patch("notifier.requests.post", mock_post):
        from notifier import send_slack_alert
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)
    mock_post.assert_not_called()


def test_send_slack_alert_non_2xx_does_not_raise(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("notifier.requests.post", return_value=mock_resp):
        from notifier import send_slack_alert
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)  # must not raise


def test_send_slack_alert_timeout_label(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    with patch("notifier.requests.post"):
        from notifier import send_slack_alert
        import io, sys
        send_slack_alert(FAILURES_TIMEOUT, "2026-05-13", total=7, dry_run=True)


def test_send_slack_alert_timeout_label_text(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    from notifier import send_slack_alert
    send_slack_alert(FAILURES_TIMEOUT, "2026-05-13", total=7, dry_run=True)
    out = capsys.readouterr().out
    assert "timeout" in out


def test_send_slack_alert_two_failures(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    from notifier import send_slack_alert
    send_slack_alert(FAILURES_TWO, "2026-05-13", total=7, dry_run=True)
    out = capsys.readouterr().out
    assert "2/7 jobs failed" in out
    assert "exit 1" in out
    assert "timeout" in out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_notifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'notifier'`

- [ ] **Step 3: Create `notifier.py`**

```python
from __future__ import annotations
import logging
import os
import requests

logger = logging.getLogger(__name__)


def send_slack_alert(
    failures: list[dict],
    run_date: str,
    total: int,
    dry_run: bool = False,
) -> None:
    n = len(failures)
    lines = [f":rotating_light: NayzFreedom Scheduler — {n}/{total} jobs failed ({run_date})", ""]
    for f in failures:
        label = f"exit {f['exit_code']}" if f["exit_code"] is not None else "timeout"
        lines.append(f"• {f['project']} | {f['brief']} | {f['content_type']} → {label}")
    message = "\n".join(lines)

    if dry_run:
        print(message)
        return

    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack alert")
        return

    try:
        resp = requests.post(url, json={"text": message}, timeout=10)
        if resp.status_code >= 300:
            logger.warning("Slack webhook returned %s", resp.status_code)
    except Exception as exc:
        logger.warning("Slack alert failed: %s", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notifier.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: add notifier.py with send_slack_alert for end-of-run failure alerts"
```

---

### Task 2: Wire `notifier.py` into `scheduler.py`

**Files:**
- Modify: `scheduler.py`
- Modify: `tests/test_scheduler.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing tests**

Add these two tests to the bottom of `tests/test_scheduler.py`:

```python
def test_scheduler_calls_notifier_on_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    results = [_make_fail_result()] + [_make_ok_result()] * 6
    with patch("scheduler.subprocess.run", side_effect=results), \
         patch("scheduler.send_slack_alert") as mock_alert:
        sched_module.run_scheduler(dry_run=False, root=tmp_path)
    mock_alert.assert_called_once()
    failures = mock_alert.call_args[0][0]
    assert len(failures) == 1
    assert failures[0]["project"] == "slay_hack"
    assert failures[0]["brief"] == "short_video_1"
    assert failures[0]["content_type"] == "video"
    assert failures[0]["exit_code"] == 1


def test_scheduler_does_not_call_notifier_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()), \
         patch("scheduler.send_slack_alert") as mock_alert:
        sched_module.run_scheduler(dry_run=False, root=tmp_path)
    mock_alert.assert_not_called()
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
pytest tests/test_scheduler.py::test_scheduler_calls_notifier_on_failure tests/test_scheduler.py::test_scheduler_does_not_call_notifier_on_success -v
```

Expected: FAIL — `scheduler` has no `send_slack_alert`

- [ ] **Step 3: Update `scheduler.py`**

Add import at the top (after existing imports):

```python
from notifier import send_slack_alert
```

Replace the `run_scheduler` function body — change `any_failed = False` setup and add failure accumulation + end-of-run alert. The full updated `run_scheduler`:

```python
def run_scheduler(dry_run: bool = False, root: Path | None = None) -> int:
    _root = root if root is not None else _ROOT
    calendars = sorted(_root.glob("projects/*/weekly_calendar.yaml"))
    if not calendars:
        logger.warning("No weekly_calendar.yaml found under projects/")
        return 0

    today = _today_name()
    run_date = datetime.now().strftime("%Y-%m-%d")
    failures: list[dict] = []
    total = 0

    for calendar_path in calendars:
        project_slug = calendar_path.parent.name
        with open(calendar_path) as f:
            calendar: dict = yaml.safe_load(f) or {}

        day_entry: dict = calendar.get(today, {})
        if not day_entry:
            logger.warning("No calendar entry for %s in %s — skipping", today, calendar_path)
            continue

        for key in _BRIEF_KEYS:
            brief = day_entry.get(key, "")
            if not brief:
                logger.warning("Blank brief for key=%s project=%s — skipping", key, project_slug)
                continue

            content_type = _KEY_TO_CONTENT_TYPE[key]
            total += 1
            cmd = [
                sys.executable, "main.py",
                "--project", project_slug,
                "--brief", brief,
                "--content-type", content_type,
                "--schedule",
                "--unattended",
            ]
            if dry_run:
                cmd.append("--dry-run")

            logger.info("Running: project=%s key=%s content_type=%s", project_slug, key, content_type)
            try:
                result = subprocess.run(cmd, cwd=_root, timeout=1800)
            except subprocess.TimeoutExpired as exc:
                if exc.process:
                    exc.process.kill()
                    exc.process.communicate()
                logger.error("TIMEOUT: project=%s key=%s", project_slug, key)
                failures.append({"project": project_slug, "brief": key, "content_type": content_type, "exit_code": None})
                continue
            if result.returncode != 0:
                logger.error("FAILED: project=%s key=%s brief=%r", project_slug, key, brief)
                failures.append({"project": project_slug, "brief": key, "content_type": content_type, "exit_code": result.returncode})
            else:
                logger.info("OK: project=%s key=%s", project_slug, key)

    if failures:
        send_slack_alert(failures, run_date, total, dry_run=dry_run)

    return 1 if failures else 0
```

Note: `any_failed` is replaced by `bool(failures)`.

- [ ] **Step 4: Add `SLACK_WEBHOOK_URL` to `.env.example`**

Open `.env.example` and append:

```
SLACK_WEBHOOK_URL=
```

- [ ] **Step 5: Run the new tests**

```bash
pytest tests/test_scheduler.py::test_scheduler_calls_notifier_on_failure tests/test_scheduler.py::test_scheduler_does_not_call_notifier_on_success -v
```

Expected: both PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass. Verify existing `test_scheduler_continues_after_failure` and `test_scheduler_timeout_continues_and_sets_exit_1` still pass (they patch `subprocess.run` only — `send_slack_alert` will be called but that's fine since it hits the real env-var guard and returns silently).

- [ ] **Step 7: Commit**

```bash
git add scheduler.py tests/test_scheduler.py .env.example
git commit -m "feat: wire send_slack_alert into scheduler for end-of-run failure notifications"
```
