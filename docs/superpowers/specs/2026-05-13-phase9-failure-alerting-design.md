# Phase 9: Failure Alerting — Design Spec

**Date:** 2026-05-13
**Phase:** 9
**Status:** Approved

---

## Goal

Notify via Slack webhook when `scheduler.py` completes a run with one or more failed jobs. One message per run (end-of-run summary), not per-job noise.

---

## Scope

- New `notifier.py` module with a single public function: `send_slack_alert`
- `scheduler.py` accumulates failures and calls `send_slack_alert` at end of run
- `--dry-run` mode prints the Slack payload to stdout instead of POSTing
- Missing `SLACK_WEBHOOK_URL` logs a warning and skips silently — never crashes the scheduler
- No alert when all jobs succeed

---

## New File: `notifier.py`

Single responsibility: format and send a Slack webhook message.

```python
def send_slack_alert(
    failures: list[dict],
    run_date: str,
    total: int,
    dry_run: bool = False,
) -> None
```

**`failures` dict shape:**
```python
{
    "project": "slay_hack",
    "brief": "article_1",
    "content_type": "article",
    "exit_code": 1,         # int or None (timeout)
}
```

**Reads:** `SLACK_WEBHOOK_URL` from `os.environ`. If missing, logs warning to stderr and returns.

**Slack message format:**
```
:rotating_light: NayzFreedom Scheduler — 2/7 jobs failed (2026-05-13)

• slay_hack | article_1 | article → exit 1
• slay_hack | short_video_1 | video → timeout
```

- Exit code displayed as `exit <N>` or `timeout` (when `exit_code` is `None`)
- `dry_run=True` prints the formatted text to stdout instead of POSTing

**HTTP:** `requests.post(url, json={"text": message}, timeout=10)`. Logs a warning on non-2xx but does not raise.

---

## Changes to `scheduler.py`

1. Add `failures: list[dict] = []` accumulator at start of `run_scheduler()`
2. On each subprocess failure (non-zero exit or timeout), append a failure dict
3. After the job loop, if `failures`: call `send_slack_alert(failures, run_date, total, dry_run)`

**`run_date`:** `datetime.date.today().isoformat()` computed once at start of `run_scheduler()`.
**`total`:** total number of briefs attempted across all projects.

---

## Environment

`.env.example` gains:
```
SLACK_WEBHOOK_URL=
```

Slack webhook URL is obtained from Slack app settings (Incoming Webhooks). Optional — system degrades gracefully without it.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `SLACK_WEBHOOK_URL` not set | Log warning to stderr, skip alert |
| Slack POST returns non-2xx | Log warning to stderr, do not raise |
| Slack POST times out | Log warning to stderr, do not raise |
| `requests` not installed | `ImportError` logged, alert skipped |
| All jobs succeed | No alert sent |

---

## Testing

`tests/test_notifier.py`:
- `test_send_slack_alert_dry_run_prints_message` — dry_run=True, capsys captures output, checks project/brief/exit code in text
- `test_send_slack_alert_posts_to_webhook` — mocks `requests.post`, verifies URL + payload text
- `test_send_slack_alert_missing_env_skips(monkeypatch)` — unsets `SLACK_WEBHOOK_URL`, verifies no POST
- `test_send_slack_alert_non_2xx_does_not_raise` — mock returns 500, assert no exception raised
- `test_send_slack_alert_timeout_label` — failure with `exit_code=None` shows "timeout" in message

`tests/test_scheduler.py` gains:
- `test_scheduler_calls_notifier_on_failure` — mock `notifier.send_slack_alert`, verify called with correct failures list when a subprocess returns exit 1
- `test_scheduler_does_not_call_notifier_on_success` — all subprocesses succeed, verify `send_slack_alert` not called

---

## Files Touched

| File | Action |
|---|---|
| `notifier.py` | Create |
| `scheduler.py` | Modify — add failure accumulator + alert call |
| `.env.example` | Modify — add `SLACK_WEBHOOK_URL=` |
| `tests/test_notifier.py` | Create |
| `tests/test_scheduler.py` | Modify — add 2 tests |

---

## Out of Scope

- Per-job alerts (too noisy)
- Success notifications
- PagerDuty / email / other channels
- Alert deduplication / rate limiting
- Slack rich attachments / Block Kit formatting
