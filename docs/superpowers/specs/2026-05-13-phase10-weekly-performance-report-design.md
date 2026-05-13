# Phase 10: Weekly Performance Report — Design Spec

**Date:** 2026-05-13
**Phase:** 10
**Status:** Approved

---

## Goal

Every Monday morning, generate a weekly performance digest covering the last 7 days of published content. Save a markdown file per brand page and send a Slack summary via the existing webhook.

---

## Scope

- New `reporter.py` standalone script with `run_reporter(dry_run, root)` function
- New `send_weekly_report(lines, dry_run)` function added to `notifier.py`
- Scans `output/<page_name>/*/job.json` for jobs from the last 7 days
- Aggregates `likes`, `reach`, `saves`, `shares` per platform
- Identifies top job by reach per platform
- Saves markdown to `output/<page_name>/weekly_report_YYYY-MM-DD.md`
- Sends Slack message using existing `SLACK_WEBHOOK_URL`
- Separate cron entry (not hooked into scheduler)

---

## New File: `reporter.py`

```
python reporter.py [--dry-run]
```

### Entry point

```python
def run_reporter(dry_run: bool = False, root: Path | None = None) -> int:
    ...
    return 0  # always 0; errors are logged, not raised
```

`root` param for testability (same pattern as `scheduler.py`).

### Data collection

Scan `output/<page_name>/*/job.json` for all pages under `root/output/`. For each job file:
- Parse `job.id[:8]` as `YYYYMMDD` to get the job date
- Include the job if the date falls within `[today - 6 days, today]` (7-day window inclusive)
- Load `job.performance` entries (list of `PostPerformance`)
- Track `job.brief` for the top-post label

Jobs with `JobStatus != COMPLETED` are included if they have performance data — status check is not used as a filter.

Jobs with empty `performance` list are skipped silently.

### Aggregation

For each job, select the **latest `PostPerformance` entry per platform** (by `recorded_at` descending; if `recorded_at` is `None`, use the last entry in the list). This prevents double-counting when the tracker records multiple snapshots for the same job.

Per `(page_name, platform)` group, sum the selected entries across all jobs:
- `total_likes`, `total_reach`, `total_saves`, `total_shares`
- `top_job` — the job with the highest selected `reach` value; ties broken by `job.id` (lexicographic, i.e. earliest)
- `job_count` — number of distinct jobs contributing data

### Markdown output

Saved to `root/output/<page_name>/weekly_report_YYYY-MM-DD.md` (date = today):

```markdown
# Weekly Report — <page_name> (YYYY-MM-DD → YYYY-MM-DD)

## <Platform>
- Jobs tracked: N
- Total reach: 12,400
- Total likes: 340
- Total saves: 89
- Total shares: 56
- Top post: <job_id> — "<brief>" (reach: 3,200)

## <Platform 2>
...

---
Generated: 2026-05-13
```

Numbers formatted with comma thousands separators. If no data exists for a page, write a brief "No performance data found for this period." section instead of an empty file.

### Slack message

Calls `send_weekly_report(lines, dry_run)` from `notifier.py`. The message is a condensed version of the markdown — one section per platform, same fields. Prefixed with `:bar_chart:`.

Example:
```
:bar_chart: Weekly Report — Slay Hack Agency (2026-05-07 → 2026-05-13)

Facebook — 7 jobs
  reach: 12,400 | likes: 340 | saves: 89 | shares: 56
  Top: 20260511_060012 — "quiet luxury brands" (reach 3,200)

Instagram — 7 jobs
  reach: 9,800 | likes: 210 | saves: 44 | shares: 31
  Top: 20260512_060034 — "old money style" (reach 2,100)
```

If no data exists for any page: `":bar_chart: Weekly Report — no performance data found for 2026-05-07 → 2026-05-13."`

---

## Changes to `notifier.py`

Add one new public function:

```python
def send_weekly_report(lines: list[str], dry_run: bool = False) -> None:
```

- `lines` is a list of strings that will be joined with `\n`
- Same behaviour as `send_slack_alert`: reads `SLACK_WEBHOOK_URL`, warns and returns if missing, POSTs `{"text": message}`, logs non-2xx as warning, never raises

---

## `CLAUDE.md` update

Add to Common Commands:
```bash
# Run weekly reporter manually
python reporter.py

# Weekly reporter dry-run (no Slack POST, prints to stdout)
python reporter.py --dry-run
```

Add cron entry note:
```
# Cron entry for VPS (8 AM every Monday)
# 0 8 * * 1 /path/to/.venv/bin/python /path/to/reporter.py >> /var/log/nayzfreedom.log 2>&1
```

---

## Error handling

| Scenario | Behaviour |
|---|---|
| `output/` doesn't exist | Log warning, return 0 |
| Corrupt `job.json` | Skip file, log warning, continue |
| No jobs in last 7 days | Write "no data" section, send "no data" Slack message |
| `SLACK_WEBHOOK_URL` not set | Log warning, skip Slack (file still written) |
| Slack POST fails | Log warning, do not raise (file still written) |
| `output/<page>/weekly_report_*.md` write fails | Log error, continue with Slack |

`run_reporter` always returns 0 — reporter failures are non-critical.

---

## Testing

`tests/test_reporter.py`:
- `test_reporter_aggregates_jobs_in_window` — 3 jobs within 7 days + 1 outside, verify only 3 counted
- `test_reporter_aggregates_metrics_by_platform` — 2 jobs with Facebook perf, verify totals summed
- `test_reporter_identifies_top_job_by_reach` — 2 jobs, top job has higher reach
- `test_reporter_writes_markdown_file` — verify file created at correct path with correct content
- `test_reporter_no_data_writes_no_data_section` — no jobs in window, verify "no data" in file
- `test_reporter_calls_send_weekly_report` — mock `send_weekly_report`, verify called with non-empty lines
- `test_reporter_dry_run_does_not_post` — dry_run=True, mock notifier, verify no POST

`tests/test_notifier.py` gains:
- `test_send_weekly_report_dry_run_prints` — dry_run=True, capsys captures output
- `test_send_weekly_report_posts_to_webhook` — mocks `requests.post`, verifies call

---

## Files Touched

| File | Action |
|---|---|
| `reporter.py` | Create |
| `notifier.py` | Modify — add `send_weekly_report` |
| `CLAUDE.md` | Modify — add commands and cron note |
| `tests/test_reporter.py` | Create |
| `tests/test_notifier.py` | Modify — add 2 tests |

---

## Out of Scope

- Per-content-type breakdown (video vs article performance)
- Trend comparison vs previous week
- Chart/graph generation
- Email delivery
- Notion integration
- Automated Monday trigger (cron entry documented, not automated)
