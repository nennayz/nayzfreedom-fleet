# Phase 8: Scheduled Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the NayzFreedom pipeline unattended via system cron, publishing 7 content pieces per brand per day (2 short video, 1 long video, 2 article, 2 infographic) from a weekly YAML content calendar.

**Architecture:** `scheduler.py` discovers brand folders, reads each brand's `weekly_calendar.yaml`, picks today's 7 briefs, and fires `main.py` as a subprocess for each — one per content type. `main.py` gains `--content-type` (pre-sets `job.content_type` before Zoe runs) and `--unattended` (auto-approves all 4 checkpoints so the pipeline runs without stdin). `checkpoint.py` gains an `unattended` parameter that skips `input()`.

**Tech Stack:** Python 3.9+, PyYAML (already in requirements via project_loader), subprocess, system cron

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `checkpoint.py` | Add `unattended: bool = False` param; auto-approve when set |
| Modify | `main.py` | Add `--content-type` and `--unattended` args; wire to job and orchestrator |
| Modify | `orchestrator.py` | Accept and forward `unattended` to `pause()` calls |
| Create | `projects/slay_hack/weekly_calendar.yaml` | Example weekly calendar (7 days × 7 briefs) |
| Create | `scheduler.py` | Discover brands, load calendar, fire subprocesses |
| Modify | `tests/test_checkpoint.py` | Add unattended mode tests |
| Create | `tests/test_scheduler.py` | All scheduler tests |

---

## Task 1: Unattended mode in `checkpoint.py`

**Files:**
- Modify: `checkpoint.py`
- Modify: `tests/test_checkpoint.py`

Context: `checkpoint.pause()` currently calls `input()` which blocks forever when run from cron (no stdin). We add `unattended: bool = False`. When `True`, skip `input()` and return a synthetic decision: `"1"` at `idea_selection` (picks the first idea), `"approved"` at all other stages.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_checkpoint.py`:

```python
def test_pause_unattended_idea_selection_returns_1():
    job = make_job()
    result = pause("idea_selection", "Pick an idea.", ["Idea A", "Idea B"], job, unattended=True)
    assert result.decision == "1"
    assert result.stage == "idea_selection"
    assert len(job.checkpoint_log) == 1
    assert job.checkpoint_log[0].decision == "1"


def test_pause_unattended_other_stages_returns_approved():
    job = make_job()
    for stage in ("content_review", "qa_review", "final_approval"):
        job.checkpoint_log.clear()
        result = pause(stage, "summary", [], job, unattended=True)
        assert result.decision == "approved"
        assert result.stage == stage


def test_pause_unattended_does_not_call_input(monkeypatch):
    called = []
    monkeypatch.setattr("builtins.input", lambda _: called.append(1) or "x")
    job = make_job()
    pause("qa_review", "summary", [], job, unattended=True)
    assert called == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_checkpoint.py::test_pause_unattended_idea_selection_returns_1 tests/test_checkpoint.py::test_pause_unattended_other_stages_returns_approved tests/test_checkpoint.py::test_pause_unattended_does_not_call_input -v
```

Expected: FAIL with `TypeError: pause() got an unexpected keyword argument 'unattended'`

- [ ] **Step 3: Update `checkpoint.py`**

Replace the entire file with:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from models.content_job import ContentJob, CheckpointDecision


@dataclass
class CheckpointResult:
    stage: str
    decision: str


def pause(
    stage: str,
    summary: str,
    options: list[str],
    job: ContentJob,
    unattended: bool = False,
) -> CheckpointResult:
    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {stage.upper().replace('_', ' ')}")
    print(f"{'='*60}")
    print(f"\n{summary}\n")

    if unattended:
        decision = "1" if stage == "idea_selection" else "approved"
        print(f"  [unattended] auto-decision: {decision}")
    else:
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  [{i}] {opt}")
        print()
        decision = input("Your choice (or type freely): ").strip()

    job.checkpoint_log.append(
        CheckpointDecision(stage=stage, decision=decision, timestamp=datetime.now())
    )
    return CheckpointResult(stage=stage, decision=decision)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_checkpoint.py -v
```

Expected: all PASS (existing tests still pass because `unattended` defaults to `False`)

- [ ] **Step 5: Commit**

```bash
git add checkpoint.py tests/test_checkpoint.py
git commit -m "feat(checkpoint): add unattended mode — auto-approve without stdin"
```

---

## Task 2: `--content-type` and `--unattended` flags in `main.py` + `orchestrator.py`

**Files:**
- Modify: `main.py`
- Modify: `orchestrator.py`
- Modify: `tests/test_checkpoint.py` (add orchestrator wiring test)

Context: `main.py` needs two new args. `--content-type` pre-sets `job.content_type` before the orchestrator runs (so Zoe generates ideas of the right type). `--unattended` must be forwarded into `Orchestrator.run()` so it reaches every `pause()` call inside `_dispatch`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_checkpoint.py` (reuses `make_job` already defined there):

```python
import sys
import main as main_module
from models.content_job import ContentType
from job_store import save_job


def test_main_content_type_flag_sets_job_content_type(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_orch = mocker.patch.object(main_module.Orchestrator, "run", return_value=make_job())
    mocker.patch.object(main_module.Config, "from_env", return_value=mocker.MagicMock(spec=main_module.Config))
    mocker.patch("main_module.load_project", return_value=make_job().pm)
    sys.argv = ["main.py", "--project", "slay_hack", "--brief", "test", "--content-type", "article"]
    try:
        main_module.main()
    except SystemExit:
        pass
    call_args = mock_orch.call_args
    job_arg = call_args[0][0]
    assert job_arg.content_type == ContentType.ARTICLE


def test_main_unattended_flag_passed_to_orchestrator(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_run = mocker.patch.object(main_module.Orchestrator, "run", return_value=make_job())
    mocker.patch.object(main_module.Config, "from_env", return_value=mocker.MagicMock(spec=main_module.Config))
    mocker.patch("main_module.load_project", return_value=make_job().pm)
    sys.argv = ["main.py", "--project", "slay_hack", "--brief", "test", "--unattended"]
    try:
        main_module.main()
    except SystemExit:
        pass
    _, kwargs = mock_run.call_args
    assert kwargs.get("unattended") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_checkpoint.py::test_main_content_type_flag_sets_job_content_type tests/test_checkpoint.py::test_main_unattended_flag_passed_to_orchestrator -v
```

Expected: FAIL — `main.py` doesn't have `--content-type` or `--unattended` yet.

- [ ] **Step 3: Update `main.py`**

Add two new `parser.add_argument` lines after line 28 (`--schedule`):

```python
    parser.add_argument(
        "--content-type",
        choices=["video", "article", "image", "infographic"],
        dest="content_type",
        help="Pre-set content type (used by scheduler to skip AI inference)",
    )
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="Auto-approve all checkpoints — required when running from cron",
    )
```

After the `job = ContentJob(...)` block (around line 104), add:

```python
        if args.content_type:
            from models.content_job import ContentType as CT
            job.content_type = CT(args.content_type)
```

Change the orchestrator call (line 111) from:

```python
    result = orchestrator.run(job)
```

to:

```python
    result = orchestrator.run(job, unattended=args.unattended)
```

- [ ] **Step 4: Update `orchestrator.py`**

Change `Orchestrator.run` signature from:

```python
    def run(self, job: ContentJob) -> ContentJob:
```

to:

```python
    def run(self, job: ContentJob, unattended: bool = False) -> ContentJob:
```

Change the `pause(...)` call inside `_dispatch` (around line 104) from:

```python
            result = pause(
                stage=tool_input.get("stage"),
                summary=tool_input.get("summary"),
                options=tool_input.get("options", []),
                job=job,
            )
```

to:

```python
            result = pause(
                stage=tool_input.get("stage"),
                summary=tool_input.get("summary"),
                options=tool_input.get("options", []),
                job=job,
                unattended=self._unattended,
            )
```

Store `unattended` on the instance at the start of `run`:

```python
    def run(self, job: ContentJob, unattended: bool = False) -> ContentJob:
        self._unattended = unattended
        job.status = JobStatus.RUNNING
        # ... rest of method unchanged
```

- [ ] **Step 5: Run all checkpoint tests**

```bash
python3 -m pytest tests/test_checkpoint.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add main.py orchestrator.py tests/test_checkpoint.py
git commit -m "feat(main): add --content-type and --unattended flags"
```

---

## Task 3: Weekly calendar YAML

**Files:**
- Create: `projects/slay_hack/weekly_calendar.yaml`

No tests needed — pure data file. The scheduler tests in Task 4 will validate parsing.

- [ ] **Step 1: Create the file**

```yaml
monday:
  short_video_1: "15-40sec Reel: morning routine for a minimalist aesthetic"
  short_video_2: "15-40sec Reel: 5 quiet luxury outfit ideas for everyday"
  long_video: "1-3min video: complete quiet luxury wardrobe guide"
  article_1: "5 quiet luxury brands Gen Z actually wears"
  article_2: "why old money style is the new flex"
  infographic_1: "quiet luxury color palette guide"
  infographic_2: "capsule wardrobe checklist"

tuesday:
  short_video_1: "15-40sec Reel: how to style beige without looking boring"
  short_video_2: "15-40sec Reel: minimalist accessories that look expensive"
  long_video: "1-3min video: quiet luxury vs old money — full breakdown"
  article_1: "the quiet luxury wardrobe checklist every girl needs"
  article_2: "brands duping The Row that actually deliver"
  infographic_1: "how to build a capsule wardrobe in 10 pieces"
  infographic_2: "quiet luxury vs old money — visual comparison"

wednesday:
  short_video_1: "15-40sec Reel: 3 ways to wear a beige trench coat"
  short_video_2: "15-40sec Reel: soft girl aesthetic morning routine"
  long_video: "1-3min video: shop my quiet luxury wardrobe under $200"
  article_1: "the accessories that make any outfit look expensive"
  article_2: "how to dress expensive on a budget — quiet luxury edition"
  infographic_1: "quiet luxury outfit formula cheat sheet"
  infographic_2: "affordable dupes for The Row, Toteme, and Khaite"

thursday:
  short_video_1: "15-40sec Reel: minimalist makeup routine for a polished look"
  short_video_2: "15-40sec Reel: quiet luxury shoe rotation"
  long_video: "1-3min video: how I built my dream capsule wardrobe"
  article_1: "weekend outfit formulas for the aesthetic girl"
  article_2: "why less is always more in quiet luxury fashion"
  infographic_1: "quiet luxury shoe guide by occasion"
  infographic_2: "bag investment guide — what's worth it"

friday:
  short_video_1: "15-40sec Reel: GRWM — quiet luxury office look"
  short_video_2: "15-40sec Reel: 5 pieces that elevated my whole wardrobe"
  long_video: "1-3min video: haul + try-on — quiet luxury finds this week"
  article_1: "what I'm buying this season and why"
  article_2: "the quiet luxury girl's guide to shopping smart"
  infographic_1: "end-of-week outfit recap — quiet luxury edition"
  infographic_2: "shopping checklist for the minimalist wardrobe"

saturday:
  short_video_1: "15-40sec Reel: weekend casual quiet luxury look"
  short_video_2: "15-40sec Reel: how to look polished running errands"
  long_video: "1-3min video: get ready with me — quiet luxury edition"
  article_1: "reset routine for the girl who has taste"
  article_2: "how to declutter your wardrobe the quiet luxury way"
  infographic_1: "weekend outfit ideas for the aesthetic girl"
  infographic_2: "wardrobe declutter checklist"

sunday:
  short_video_1: "15-40sec Reel: slow morning routine — quiet luxury vibes"
  short_video_2: "15-40sec Reel: what I'm wearing this week"
  long_video: "1-3min video: weekly content prep and wardrobe reset"
  article_1: "what I'm buying this week and why"
  article_2: "the sunday reset guide for the aesthetic girl"
  infographic_1: "weekly wardrobe plan — quiet luxury edition"
  infographic_2: "self-care routine for the girl who has it together"
```

- [ ] **Step 2: Commit**

```bash
git add projects/slay_hack/weekly_calendar.yaml
git commit -m "feat(scheduler): add weekly content calendar for slay_hack"
```

---

## Task 4: `scheduler.py` + `tests/test_scheduler.py`

**Files:**
- Create: `scheduler.py`
- Create: `tests/test_scheduler.py`

Context: `scheduler.py` discovers all `projects/*/weekly_calendar.yaml` files, loads today's day entry, and fires `python main.py` as a subprocess for each of the 7 brief keys. The key name determines `--content-type`. `--dry-run` is forwarded if passed. Always passes `--unattended` and `--schedule`.

Brief key → content-type mapping:
- `short_video_1`, `short_video_2`, `long_video` → `video`
- `article_1`, `article_2` → `article`
- `infographic_1`, `infographic_2` → `infographic`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheduler.py`:

```python
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import call, patch, MagicMock
import pytest
import scheduler as sched_module


MONDAY_CALENDAR = {
    "monday": {
        "short_video_1": "15-40sec Reel: morning routine",
        "short_video_2": "15-40sec Reel: 5 outfit ideas",
        "long_video": "1-3min video: wardrobe guide",
        "article_1": "quiet luxury brands",
        "article_2": "old money style",
        "infographic_1": "color palette guide",
        "infographic_2": "capsule wardrobe checklist",
    }
}


def _make_ok_result():
    r = MagicMock()
    r.returncode = 0
    return r


def _make_fail_result():
    r = MagicMock()
    r.returncode = 1
    return r


def test_scheduler_loads_todays_brief(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False)
    assert exit_code == 0
    assert mock_run.call_count == 7
    calls_flat = [c.args[0] for c in mock_run.call_args_list]
    assert any("--content-type" in str(c) and "video" in str(c) for c in calls_flat)
    assert any("--content-type" in str(c) and "article" in str(c) for c in calls_flat)
    assert any("--content-type" in str(c) and "infographic" in str(c) for c in calls_flat)


def test_scheduler_skips_missing_day(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump({"monday": MONDAY_CALENDAR["monday"]})
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "tuesday")
    with patch("scheduler.subprocess.run") as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False)
    assert mock_run.call_count == 0
    assert exit_code == 0


def test_scheduler_skips_blank_brief(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    calendar = {"monday": dict(MONDAY_CALENDAR["monday"])}
    calendar["monday"]["short_video_1"] = ""
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(calendar)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False)
    assert mock_run.call_count == 6


def test_scheduler_continues_after_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    results = [_make_fail_result()] + [_make_ok_result()] * 6
    with patch("scheduler.subprocess.run", side_effect=results) as mock_run:
        exit_code = sched_module.run_scheduler(dry_run=False)
    assert mock_run.call_count == 7
    assert exit_code == 1


def test_scheduler_dry_run_passes_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()) as mock_run:
        sched_module.run_scheduler(dry_run=True)
    for c in mock_run.call_args_list:
        assert "--dry-run" in c.args[0]


def test_scheduler_exit_code_zero_on_all_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    import yaml
    (tmp_path / "projects" / "slay_hack" / "weekly_calendar.yaml").write_text(
        yaml.dump(MONDAY_CALENDAR)
    )
    monkeypatch.setattr(sched_module, "_today_name", lambda: "monday")
    with patch("scheduler.subprocess.run", return_value=_make_ok_result()):
        exit_code = sched_module.run_scheduler(dry_run=False)
    assert exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_scheduler.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scheduler'`

- [ ] **Step 3: Create `scheduler.py`**

```python
from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_KEY_TO_CONTENT_TYPE: dict[str, str] = {
    "short_video_1": "video",
    "short_video_2": "video",
    "long_video": "video",
    "article_1": "article",
    "article_2": "article",
    "infographic_1": "infographic",
    "infographic_2": "infographic",
}

_BRIEF_KEYS = list(_KEY_TO_CONTENT_TYPE.keys())


def _today_name() -> str:
    from datetime import datetime
    return datetime.now().strftime("%A").lower()


def run_scheduler(dry_run: bool = False) -> int:
    calendars = sorted(Path("projects").glob("*/weekly_calendar.yaml"))
    if not calendars:
        logger.warning("No weekly_calendar.yaml found under projects/")
        return 0

    today = _today_name()
    any_failed = False

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
            result = subprocess.run(cmd)
            if result.returncode != 0:
                logger.error("FAILED: project=%s key=%s brief=%r", project_slug, key, brief)
                any_failed = True
            else:
                logger.info("OK: project=%s key=%s", project_slug, key)

    return 1 if any_failed else 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NayzFreedom daily content scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to each main.py call")
    args = parser.parse_args()
    sys.exit(run_scheduler(dry_run=args.dry_run))
```

- [ ] **Step 4: Run all scheduler tests**

```bash
python3 -m pytest tests/test_scheduler.py -v
```

Expected: all 6 PASS

- [ ] **Step 5: Run full publish test suite to check for regressions**

```bash
python3 -m pytest tests/test_checkpoint.py tests/test_scheduler.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): add daily content scheduler with weekly YAML calendar"
```

---

## Task 5: Verify and final commit

**Files:** none new — smoke-test and document cron setup

- [ ] **Step 1: Smoke-test dry-run manually**

```bash
python3 scheduler.py --dry-run
```

Expected output (no real API calls):
```
2026-05-13 06:00:00 [INFO] Running: project=slay_hack key=short_video_1 content_type=video
2026-05-13 06:00:00 [INFO] Running: project=slay_hack key=short_video_2 content_type=video
...
```
(Pipeline will start and hit mock mode for each job)

- [ ] **Step 2: Run the full test suite for all touched files**

```bash
python3 -m pytest tests/test_checkpoint.py tests/test_scheduler.py -v
```

Expected: all PASS

- [ ] **Step 3: Run ruff**

```bash
python3 -m ruff check scheduler.py checkpoint.py main.py orchestrator.py
```

Expected: no issues

- [ ] **Step 4: Document cron setup**

Add to `CLAUDE.md` under **Common Commands**:

```bash
# Run scheduler manually (dry-run)
python scheduler.py --dry-run

# Cron entry for VPS (6 AM daily, logs to /var/log/nayzfreedom.log)
# 0 6 * * * /path/to/.venv/bin/python /path/to/scheduler.py >> /var/log/nayzfreedom.log 2>&1
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add scheduler cron setup to CLAUDE.md"
```
