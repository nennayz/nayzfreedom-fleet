# Phase 8: Scheduled Automation Design

## Goal

Run the NayzFreedom pipeline unattended on a VPS, publishing 7 content pieces per brand per day from a pre-defined weekly content calendar.

## Daily Content Mix (per brand)

| Key | Content Type | Duration/Format | Count |
|---|---|---|---|
| `short_video_1`, `short_video_2` | VIDEO | 15–40 sec Reel | 2 |
| `long_video` | VIDEO | 1–3 min | 1 |
| `article_1`, `article_2` | ARTICLE | — | 2 |
| `infographic_1`, `infographic_2` | INFOGRAPHIC | — | 2 |

**Total:** 7 jobs/brand/day → 49 jobs/brand/week.

## Scope

- Add `scheduler.py` — new entry-point script
- Add `projects/slay_hack/weekly_calendar.yaml` — example weekly calendar (template for all brands)
- Add `--content-type` flag to `main.py` — pre-sets `job.content_type` before Zoe runs (required so scheduler doesn't depend on AI inferring type from brief text)
- Add `--unattended` flag to `main.py` — auto-approves all checkpoints so the pipeline runs without stdin
- Modify `checkpoint.py` — respect `unattended` mode: auto-select first idea matching content type at `idea_selection`; log and continue at all other checkpoints
- Add `tests/test_scheduler.py`
- No changes to any agent, orchestrator, or model

## Architecture

```
cron (6 AM daily)
  └── scheduler.py [--dry-run]
        ├── discover: glob("projects/*/weekly_calendar.yaml")
        └── for each brand:
              load weekly_calendar.yaml
              get today's day name (monday … sunday)
              for each of 7 brief keys:
                subprocess: python main.py --project <slug>
                                           --brief "<brief>"
                                           --content-type <type>
                                           --schedule
                                           --unattended
                                           [--dry-run]
              log result (success / failure)
```

Each subprocess is independent — one failure never blocks the rest.

## Cron Entry (VPS)

```
0 6 * * * /path/to/.venv/bin/python /path/to/scheduler.py --schedule >> /var/log/nayzfreedom.log 2>&1
```

Fires at 6 AM daily. Roxy's `--schedule` flag publishes at the optimal time (typically afternoon/evening), giving 4–12 hours of buffer for generation and QA retries.

## Weekly Calendar Format

`projects/<brand>/weekly_calendar.yaml`:

```yaml
monday:
  short_video_1: "15-40sec Reel: morning routine for a minimalist aesthetic"
  short_video_2: "15-40sec Reel: 5 outfit ideas for the quiet luxury girl"
  long_video: "1-3min video: complete quiet luxury wardrobe guide"
  article_1: "5 quiet luxury brands Gen Z actually wears"
  article_2: "why old money style is the new flex"
  infographic_1: "quiet luxury color palette guide"
  infographic_2: "capsule wardrobe checklist"
tuesday:
  short_video_1: "..."
  # ... etc
```

Brief keys map to content types:

| Key pattern | `--content-type` |
|---|---|
| `short_video_*`, `long_video` | `video` |
| `article_*` | `article` |
| `infographic_*` | `infographic` |

## Content-Type Flag (`main.py`)

New argument `--content-type` (choices: `video`, `article`, `image`, `infographic`). When provided, sets `job.content_type` immediately after job creation, before the orchestrator runs. Zoe still generates ideas, but with the type pre-constrained via the system prompt context Robin passes.

## Unattended Flag (`main.py` + `checkpoint.py`)

New boolean argument `--unattended` on `main.py`. When set, passed into `checkpoint.pause()` via a parameter. Checkpoint behaviour in unattended mode:

| Stage | Unattended behaviour |
|---|---|
| `idea_selection` | Auto-select the first idea whose `content_type` matches `job.content_type`. If none match, select the first idea overall. Log the auto-selected idea title. |
| `content_review` | Log summary and continue — no user input |
| `qa_review` | Log summary and continue — no user input |
| `final_approval` | Log summary and continue — no user input |

`checkpoint.pause()` signature gains an `unattended: bool = False` parameter. All existing callers pass the default, so interactive mode is unchanged.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Day not in calendar | Log warning, skip brand for today — no crash |
| Brief value is blank or missing | Log warning, skip that content slot |
| Subprocess exits non-zero | Log error with brief and platform, continue to next job |
| All 7 jobs succeed | Exit 0 |
| Any job failed | Exit 1 (cron can email on non-zero exit) |

## Testing

All tests in `tests/test_scheduler.py`. `subprocess.run` is mocked in all tests — no actual pipeline execution.

| Test | What it verifies |
|---|---|
| `test_scheduler_loads_todays_brief` | Mock today = `"monday"`, verify 7 subprocess calls with correct `--brief` and `--content-type` args |
| `test_scheduler_skips_missing_day` | Calendar has no entry for today → 0 subprocess calls, no exception |
| `test_scheduler_skips_blank_brief` | One brief value is `""` → that slot skipped, rest proceed |
| `test_scheduler_continues_after_failure` | One subprocess returns exit code 1 → remaining 6 jobs still called |
| `test_scheduler_dry_run_passes_flag` | `--dry-run` forwarded to every `main.py` call |
| `test_scheduler_exit_code_on_failure` | Any failed job → `scheduler.py` exits with code 1 |
| `test_main_content_type_flag` | `--content-type video` sets `job.content_type = ContentType.VIDEO` before orchestrator runs |
| `test_main_unattended_flag` | `--unattended` passed to orchestrator; `checkpoint.pause()` returns auto-decision without calling `input()` |
| `test_checkpoint_unattended_idea_selection` | Auto-selects first idea matching content_type; falls back to first idea if no match |
| `test_checkpoint_unattended_other_stages` | `content_review`, `qa_review`, `final_approval` return auto-approve decision without calling `input()` |

## Files

| Action | Path |
|---|---|
| Create | `scheduler.py` |
| Create | `projects/slay_hack/weekly_calendar.yaml` |
| Modify | `main.py` (add `--content-type` and `--unattended` arguments) |
| Modify | `checkpoint.py` (add `unattended` parameter to `pause()`) |
| Create | `tests/test_scheduler.py` |
