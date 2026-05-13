# Phase 10: Weekly Performance Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a weekly performance digest (markdown file + Slack message) summarising the last 7 days of published content metrics across all brand pages.

**Architecture:** New `reporter.py` standalone script with `run_reporter(dry_run, root)` following the same pattern as `scheduler.py`. New `send_weekly_report` added to `notifier.py`. Data collected from `output/<page>/*/job.json`, aggregated using latest snapshot per (job, platform), then formatted to markdown + Slack.

**Tech Stack:** Python stdlib (`dataclasses`, `datetime`, `pathlib`), Pydantic (`ContentJob`), `requests` (via `notifier.py`), `pytest`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `notifier.py` | Modify | Add `send_weekly_report(lines, dry_run)` |
| `reporter.py` | Create | All report logic: data collection, aggregation, formatting, output |
| `CLAUDE.md` | Modify | Add reporter commands + cron entry |
| `tests/test_notifier.py` | Modify | Add 2 tests for `send_weekly_report` |
| `tests/test_reporter.py` | Create | 7 tests for reporter logic |

---

### Task 1: Add `send_weekly_report` to `notifier.py`

**Files:**
- Modify: `notifier.py`
- Modify: `tests/test_notifier.py`

- [ ] **Step 1: Write the failing tests**

Add these two tests at the bottom of `tests/test_notifier.py`:

```python
def test_send_weekly_report_dry_run_prints(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    from notifier import send_weekly_report
    send_weekly_report([":bar_chart: Weekly Report", "", "Facebook — 3 jobs"], dry_run=True)
    out = capsys.readouterr().out
    assert ":bar_chart: Weekly Report" in out
    assert "Facebook — 3 jobs" in out


def test_send_weekly_report_posts_to_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_post = MagicMock()
    mock_post.return_value.__enter__ = lambda s: mock_post.return_value
    mock_post.return_value.__exit__ = MagicMock(return_value=False)
    mock_post.return_value.status_code = 200
    with patch("notifier.requests.post", mock_post):
        from notifier import send_weekly_report
        send_weekly_report([":bar_chart: Weekly Report", "Facebook — 3 jobs"], dry_run=False)
    mock_post.assert_called_once()
    assert ":bar_chart: Weekly Report" in mock_post.call_args.kwargs["json"]["text"]
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/python -m pytest tests/test_notifier.py::test_send_weekly_report_dry_run_prints tests/test_notifier.py::test_send_weekly_report_posts_to_webhook -v
```

Expected: `ImportError: cannot import name 'send_weekly_report'`

- [ ] **Step 3: Add `send_weekly_report` to `notifier.py`**

Add this function at the bottom of `notifier.py`:

```python
def send_weekly_report(lines: list[str], dry_run: bool = False) -> None:
    message = "\n".join(lines)

    if dry_run:
        print(message)
        return

    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("WARNING: SLACK_WEBHOOK_URL not set — skipping weekly report.", file=sys.stderr)
        return

    try:
        with requests.post(url, json={"text": message}, timeout=10) as resp:
            if not (200 <= resp.status_code < 300):
                print(
                    f"WARNING: Slack weekly report webhook returned status {resp.status_code}.",
                    file=sys.stderr,
                )
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Failed to send weekly report: {exc}", file=sys.stderr)
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_notifier.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: add send_weekly_report to notifier.py"
```

---

### Task 2: `reporter.py` — data collection and aggregation

**Files:**
- Create: `reporter.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_reporter.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from models.content_job import (
    BrandProfile, ContentJob, PMProfile, PostPerformance, VisualIdentity, JobStatus,
)


def _make_pm(page_name: str = "Slay Hack Agency") -> PMProfile:
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""), platforms=[],
        tone="", target_audience="", script_style="", nora_max_retries=2,
    )
    return PMProfile(name="Test PM", page_name=page_name, persona="", brand=brand)


def _make_job(job_id: str, brief: str = "test brief", performance=None, page_name: str = "Slay Hack Agency") -> ContentJob:
    job = ContentJob(
        id=job_id,
        project="slay_hack",
        pm=_make_pm(page_name),
        brief=brief,
        platforms=["facebook"],
        status=JobStatus.COMPLETED,
    )
    if performance is not None:
        job.performance = performance
    return job


def _write_job(tmp_path: Path, job: ContentJob) -> None:
    page_name = job.pm.page_name
    job_dir = tmp_path / "output" / page_name / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(job.model_dump_json())


TODAY = date(2026, 5, 13)
IN_WINDOW_ID = "20260510_060000"   # 3 days ago — inside window
OUT_WINDOW_ID = "20260505_060000"  # 8 days ago — outside window


def test_reporter_aggregates_jobs_in_window(tmp_path):
    job_in = _make_job(IN_WINDOW_ID, performance=[
        PostPerformance(platform="facebook", reach=1000, likes=50, saves=10, shares=5),
    ])
    job_out = _make_job(OUT_WINDOW_ID, performance=[
        PostPerformance(platform="facebook", reach=999, likes=1, saves=1, shares=1),
    ])
    _write_job(tmp_path, job_in)
    _write_job(tmp_path, job_out)

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)

    assert "Slay Hack Agency" in data
    assert data["Slay Hack Agency"]["facebook"].job_count == 1
    assert data["Slay Hack Agency"]["facebook"].total_reach == 1000


def test_reporter_aggregates_metrics_by_platform(tmp_path):
    job1 = _make_job("20260511_060000", brief="brief1", performance=[
        PostPerformance(platform="facebook", reach=1000, likes=50, saves=10, shares=5),
    ])
    job2 = _make_job("20260512_060000", brief="brief2", performance=[
        PostPerformance(platform="facebook", reach=2000, likes=100, saves=20, shares=10),
    ])
    _write_job(tmp_path, job1)
    _write_job(tmp_path, job2)

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)

    stats = data["Slay Hack Agency"]["facebook"]
    assert stats.job_count == 2
    assert stats.total_reach == 3000
    assert stats.total_likes == 150
    assert stats.total_saves == 30
    assert stats.total_shares == 15


def test_reporter_identifies_top_job_by_reach(tmp_path):
    job1 = _make_job("20260511_060000", brief="low reach post", performance=[
        PostPerformance(platform="facebook", reach=500, likes=10, saves=2, shares=1),
    ])
    job2 = _make_job("20260512_060000", brief="high reach post", performance=[
        PostPerformance(platform="facebook", reach=3000, likes=100, saves=20, shares=10),
    ])
    _write_job(tmp_path, job1)
    _write_job(tmp_path, job2)

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)

    stats = data["Slay Hack Agency"]["facebook"]
    assert stats.top_job_id == "20260512_060000"
    assert stats.top_job_brief == "high reach post"
    assert stats.top_job_reach == 3000


def test_reporter_uses_latest_snapshot_per_platform(tmp_path):
    # Same job, two snapshots for facebook — should use the later one (higher reach)
    older = PostPerformance(
        platform="facebook", reach=500, likes=10, saves=2, shares=1,
        recorded_at=datetime(2026, 5, 11, 6, 0),
    )
    newer = PostPerformance(
        platform="facebook", reach=800, likes=20, saves=5, shares=3,
        recorded_at=datetime(2026, 5, 12, 6, 0),
    )
    job = _make_job("20260511_060000", brief="snapshot test", performance=[older, newer])
    _write_job(tmp_path, job)

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)

    stats = data["Slay Hack Agency"]["facebook"]
    assert stats.total_reach == 800  # only the newer snapshot counted


def test_reporter_skips_jobs_outside_window(tmp_path):
    job = _make_job(OUT_WINDOW_ID, performance=[
        PostPerformance(platform="facebook", reach=999),
    ])
    _write_job(tmp_path, job)

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)

    assert data == {}


def test_reporter_skips_jobs_with_no_performance(tmp_path):
    job = _make_job(IN_WINDOW_ID, performance=[])
    _write_job(tmp_path, job)

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)

    assert data == {}


def test_reporter_skips_corrupt_job_file(tmp_path):
    page_dir = tmp_path / "output" / "Slay Hack Agency" / IN_WINDOW_ID
    page_dir.mkdir(parents=True)
    (page_dir / "job.json").write_text("not valid json {{{")

    from reporter import collect_week_data
    data = collect_week_data(tmp_path, TODAY)  # must not raise

    assert data == {}
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/python -m pytest tests/test_reporter.py -v
```

Expected: `ModuleNotFoundError: No module named 'reporter'`

- [ ] **Step 3: Create `reporter.py`** with data collection and aggregation

```python
from __future__ import annotations
import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from models.content_job import ContentJob, PostPerformance
from notifier import send_weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent


@dataclass
class PlatformStats:
    job_count: int = 0
    total_reach: int = 0
    total_likes: int = 0
    total_saves: int = 0
    total_shares: int = 0
    top_job_id: str = ""
    top_job_brief: str = ""
    top_job_reach: int = 0


def _in_window(job_id: str, today: date) -> bool:
    try:
        job_date = date(int(job_id[:4]), int(job_id[4:6]), int(job_id[6:8]))
        return (today - timedelta(days=6)) <= job_date <= today
    except (ValueError, IndexError):
        return False


def _latest_perf_per_platform(performances: list[PostPerformance]) -> dict[str, PostPerformance]:
    latest: dict[str, PostPerformance] = {}
    for p in performances:
        if p.platform not in latest:
            latest[p.platform] = p
        else:
            existing = latest[p.platform]
            if p.recorded_at is not None and (
                existing.recorded_at is None or p.recorded_at > existing.recorded_at
            ):
                latest[p.platform] = p
    return latest


def collect_week_data(root: Path, today: date) -> dict[str, dict[str, PlatformStats]]:
    output_dir = root / "output"
    if not output_dir.exists():
        return {}

    result: dict[str, dict[str, PlatformStats]] = {}

    for job_file in output_dir.glob("*/*/job.json"):
        page_name = job_file.parent.parent.name
        try:
            job = ContentJob.model_validate_json(job_file.read_text())
        except Exception as exc:
            logger.warning("Skipping corrupt job file %s: %s", job_file, exc)
            continue

        if not _in_window(job.id, today):
            continue

        if not job.performance:
            continue

        latest = _latest_perf_per_platform(job.performance)

        if page_name not in result:
            result[page_name] = {}

        for platform, perf in latest.items():
            if platform not in result[page_name]:
                result[page_name][platform] = PlatformStats()
            stats = result[page_name][platform]
            stats.job_count += 1
            reach = perf.reach or 0
            stats.total_reach += reach
            stats.total_likes += perf.likes or 0
            stats.total_saves += perf.saves or 0
            stats.total_shares += perf.shares or 0
            if reach > stats.top_job_reach or (
                reach == stats.top_job_reach and job.id < stats.top_job_id
            ):
                stats.top_job_id = job.id
                stats.top_job_brief = job.brief
                stats.top_job_reach = reach

    return result
```

Note: do NOT add `run_reporter`, `_format_markdown`, `_format_slack`, or the `if __name__ == "__main__"` block yet — those come in Task 3.

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_reporter.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add reporter.py tests/test_reporter.py
git commit -m "feat: add reporter.py data collection and aggregation"
```

---

### Task 3: `reporter.py` — formatting, output, and CLI

**Files:**
- Modify: `reporter.py` (add `_format_markdown`, `_format_slack`, `run_reporter`, CLI)
- Modify: `tests/test_reporter.py` (add 3 more tests)

- [ ] **Step 1: Write failing tests**

Add these three tests at the bottom of `tests/test_reporter.py`:

```python
def test_reporter_writes_markdown_file(tmp_path):
    job = _make_job("20260511_060000", brief="quiet luxury brands", performance=[
        PostPerformance(platform="facebook", reach=3200, likes=80, saves=15, shares=7),
    ])
    _write_job(tmp_path, job)

    with patch("reporter.send_weekly_report"):
        from reporter import run_reporter
        run_reporter(dry_run=True, root=tmp_path)

    report_path = tmp_path / "output" / "Slay Hack Agency" / f"weekly_report_{TODAY}.md"
    assert report_path.exists()
    content = report_path.read_text()
    assert "Weekly Report" in content
    assert "facebook" in content.lower() or "Facebook" in content
    assert "3,200" in content
    assert "quiet luxury brands" in content


def test_reporter_no_data_writes_no_data_section(tmp_path):
    # output/ exists but no job files
    (tmp_path / "output").mkdir(parents=True)

    with patch("reporter.send_weekly_report") as mock_alert:
        from reporter import run_reporter
        run_reporter(dry_run=True, root=tmp_path)

    mock_alert.assert_called_once()
    lines = mock_alert.call_args.args[0]
    assert any("no performance data" in line.lower() for line in lines)


def test_reporter_calls_send_weekly_report(tmp_path):
    # Use a job ID from today so it's always in the window
    today_id = date.today().strftime("%Y%m%d") + "_060000"
    job = _make_job(today_id, brief="test", performance=[
        PostPerformance(platform="facebook", reach=1000, likes=30, saves=5, shares=2),
    ])
    _write_job(tmp_path, job)

    with patch("reporter.send_weekly_report") as mock_send:
        from reporter import run_reporter
        run_reporter(dry_run=False, root=tmp_path)

    mock_send.assert_called()
    lines = mock_send.call_args.args[0]
    assert any(":bar_chart:" in line for line in lines)
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/python -m pytest tests/test_reporter.py::test_reporter_writes_markdown_file tests/test_reporter.py::test_reporter_no_data_writes_no_data_section tests/test_reporter.py::test_reporter_calls_send_weekly_report -v
```

Expected: `AttributeError: module 'reporter' has no attribute 'run_reporter'`

- [ ] **Step 3: Add formatting and `run_reporter` to `reporter.py`**

Append to the bottom of `reporter.py` (after `collect_week_data`):

```python
def _format_markdown(
    page_name: str,
    data: dict[str, PlatformStats],
    start_date: date,
    end_date: date,
) -> str:
    lines = [
        f"# Weekly Report — {page_name} ({start_date} → {end_date})",
        "",
    ]
    if not data:
        lines.append("No performance data found for this period.")
    else:
        for platform, stats in sorted(data.items()):
            lines += [
                f"## {platform}",
                f"- Jobs tracked: {stats.job_count}",
                f"- Total reach: {stats.total_reach:,}",
                f"- Total likes: {stats.total_likes:,}",
                f"- Total saves: {stats.total_saves:,}",
                f"- Total shares: {stats.total_shares:,}",
            ]
            if stats.top_job_id:
                lines.append(
                    f'- Top post: {stats.top_job_id} — "{stats.top_job_brief}"'
                    f" (reach: {stats.top_job_reach:,})"
                )
            lines.append("")
    lines += ["---", f"Generated: {end_date}"]
    return "\n".join(lines)


def _format_slack(
    page_name: str,
    data: dict[str, PlatformStats],
    start_date: date,
    end_date: date,
) -> list[str]:
    lines = [f":bar_chart: Weekly Report — {page_name} ({start_date} → {end_date})", ""]
    if not data:
        lines.append("No performance data found for this period.")
    else:
        for platform, stats in sorted(data.items()):
            lines.append(f"{platform} — {stats.job_count} jobs")
            lines.append(
                f"  reach: {stats.total_reach:,} | likes: {stats.total_likes:,}"
                f" | saves: {stats.total_saves:,} | shares: {stats.total_shares:,}"
            )
            if stats.top_job_id:
                lines.append(
                    f'  Top: {stats.top_job_id} — "{stats.top_job_brief}"'
                    f" (reach {stats.top_job_reach:,})"
                )
            lines.append("")
    return lines


def run_reporter(dry_run: bool = False, root: Path | None = None) -> int:
    _root = root if root is not None else _ROOT
    today = date.today()
    start_date = today - timedelta(days=6)

    all_data = collect_week_data(_root, today)

    if not all_data:
        logger.warning("No performance data found for any page in the last 7 days.")
        send_weekly_report(
            [f":bar_chart: Weekly Report — no performance data found for {start_date} → {today}."],
            dry_run=dry_run,
        )
        return 0

    for page_name, page_data in sorted(all_data.items()):
        md = _format_markdown(page_name, page_data, start_date, today)
        out_path = _root / "output" / page_name / f"weekly_report_{today}.md"
        try:
            out_path.write_text(md)
            logger.info("Report written to %s", out_path)
        except OSError as exc:
            logger.error("Failed to write report for %s: %s", page_name, exc)

        slack_lines = _format_slack(page_name, page_data, start_date, today)
        send_weekly_report(slack_lines, dry_run=dry_run)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NayzFreedom weekly performance reporter")
    parser.add_argument("--dry-run", action="store_true", help="Print Slack message to stdout instead of posting")
    args = parser.parse_args()
    sys.exit(run_reporter(dry_run=args.dry_run))
```

- [ ] **Step 4: Run the new tests**

```bash
.venv/bin/python -m pytest tests/test_reporter.py -v
```

Expected: all 10 tests PASS

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add reporter.py tests/test_reporter.py
git commit -m "feat: add run_reporter with markdown output, Slack formatting, and CLI"
```

---

### Task 4: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add reporter commands**

In `CLAUDE.md`, find the block:

```
# Run scheduler manually (dry-run — no API calls)
python scheduler.py --dry-run

# Cron entry for VPS (6 AM daily, logs to /var/log/nayzfreedom.log)
# 0 6 * * * /path/to/.venv/bin/python /path/to/scheduler.py >> /var/log/nayzfreedom.log 2>&1
```

Replace it with:

```
# Run scheduler manually (dry-run — no API calls)
python scheduler.py --dry-run

# Cron entry for VPS (6 AM daily, logs to /var/log/nayzfreedom.log)
# 0 6 * * * /path/to/.venv/bin/python /path/to/scheduler.py >> /var/log/nayzfreedom.log 2>&1

# Run weekly performance reporter (generates markdown + sends Slack digest)
python reporter.py

# Weekly reporter dry-run (prints Slack message to stdout, no POST)
python reporter.py --dry-run

# Cron entry for VPS (8 AM every Monday)
# 0 8 * * 1 /path/to/.venv/bin/python /path/to/reporter.py >> /var/log/nayzfreedom.log 2>&1
```

- [ ] **Step 2: Verify CLAUDE.md looks correct**

Open `CLAUDE.md` and confirm both cron entries appear (scheduler at 6 AM daily, reporter at 8 AM Monday) and the reporter commands are present.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add reporter.py commands and Monday cron entry to CLAUDE.md"
```
