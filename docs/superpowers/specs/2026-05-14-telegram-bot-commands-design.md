# Phase 12: Telegram Bot Command Handler — Design Spec

**Date:** 2026-05-14
**Phase:** 12
**Status:** Approved

---

## Goal

Allow the user to trigger pipeline runs directly from Telegram via a conversational bot flow, without opening the dashboard. The bot guides the user step-by-step (project → content type → dry run → brief → confirm) then spawns the pipeline. Checkpoint messages continue to work exactly as before.

---

## Scope

- `telegram_bot.py` — new file, persistent polling service with conversation state machine
- `deploy/nayzfreedom-bot.service` — new systemd unit
- `main.py` — modified to remove lock file on exit (success and failure)
- `tests/test_telegram_bot.py` — new tests
- Phase 11c features (webhook, multi-user) remain out of scope

---

## Architecture

Two coordination files:

| File | Purpose |
|---|---|
| `/tmp/nayz_pipeline.lock` | Written by bot on spawn AND by `send_and_wait()` on each checkpoint poll. Deleted by `main.py` on exit (via try/finally). Prevents bot polling during any pipeline phase regardless of how it was triggered (dashboard or Telegram). |
| `/tmp/nayz_bot_state.json` | Conversation state between messages. Expires after 10 minutes of inactivity. |

Lock file write/delete owners:
- **Bot-triggered run:** bot writes lock before `Popen`, `main.py` deletes on exit
- **Dashboard-triggered run:** `send_and_wait()` writes lock at start of each checkpoint poll, deletes on return — bot pauses automatically

`telegram_bot.py` runs as a persistent systemd service. Its poll loop:
1. Check lock file — if present and age < 4 hours, skip processing (pipeline active)
2. If lock is stale (> 4 hours), delete it and resume
3. `getUpdates(offset, timeout=5)`
4. For each update: verify chat_id, advance state machine, send response
5. Loop

`main.py` wraps `Orchestrator.run()` in try/finally to always delete the lock file.

---

## Security

- All messages from chat IDs other than `TELEGRAM_CHAT_ID` are silently ignored
- No commands are logged (prevents sensitive brief content in logs)
- Only one pipeline can run at a time (lock file guard)

---

## Conversation Flow

```
User: (any message)
Bot:  "⚡ New pipeline run. Which project?"
      [slay_hack]   ← one button per projects/ folder

User: slay_hack
Bot:  "Content type?"
      [video] [article] [image] [infographic]

User: video
Bot:  "Dry run? (no API calls — for testing)"
      [Yes — dry run] [No — real run]

User: No — real run
Bot:  "Brief? Describe the content you want."

User: 3 skincare mistakes that age your skin faster
Bot:  "Ready to start:
      📁 slay_hack | 🎬 video | 🔴 real run
      📝 3 skincare mistakes that age your skin faster

      Start pipeline?"
      [Start ✅] [Cancel ❌]

User: Start ✅
Bot:  "Pipeline started. ⏳ You'll receive checkpoint messages as it progresses."
      → writes /tmp/nayz_pipeline.lock
      → subprocess.Popen(main.py --project slay_hack --brief "..." --content-type video)
```

---

## Commands

| Command / Input | Behaviour |
|---|---|
| Any message (idle state) | Starts conversation |
| `/cancel` | Clears state, replies "Cancelled." |
| `/status` | Replies "⏳ Pipeline running." or "✅ No pipeline running." |
| Message from wrong chat_id | Silently ignored |
| Pipeline already running (lock exists) | "⏳ Pipeline is already running. Wait for the next checkpoint." |

---

## State Machine

States (stored in `/tmp/nayz_bot_state.json`):

```
idle
  → awaiting_project      (user sent any message)
  → awaiting_content_type (user picked project)
  → awaiting_dry_run      (user picked content type)
  → awaiting_brief        (user picked dry run option)
  → awaiting_confirm      (user sent brief)
  → idle                  (user confirmed or cancelled)
```

State file schema:
```json
{
  "state": "awaiting_brief",
  "project": "slay_hack",
  "content_type": "video",
  "dry_run": false,
  "brief": null,
  "updated_at": 1747224000.0
}
```

Timeout: if `now - updated_at > 600` (10 minutes), state resets to idle on next message.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `main.py` exits (success or error) | `finally` block deletes lock file |
| Lock file age > 4 hours | Bot considers it stale, deletes it, resumes |
| Bot crash / restart | Reads existing state file on startup, resumes conversation |
| `getUpdates` network error | Log warning, continue loop (same as checkpoint polling) |
| User sends `/cancel` mid-conversation | Delete state file, reply "Cancelled." |

---

## `telegram_bot.py` — Public Interface

```python
def run_bot(token: str, chat_id: str, root: Path) -> None:
    """Main entry point. Polls indefinitely. Blocks."""

def _handle_update(update: dict, token: str, chat_id: str, root: Path) -> None:
    """Process one update. Advances state machine."""

def _load_state(path: Path) -> dict:
    """Load state file. Returns idle state if missing or expired."""

def _save_state(path: Path, state: dict) -> None:
    """Write state file atomically."""

def _spawn_pipeline(state: dict, token: str, chat_id: str, root: Path) -> None:
    """Write lock file and Popen main.py."""
```

---

## `main.py` change

Wrap the orchestrator call in try/finally:

```python
lock = Path("/tmp/nayz_pipeline.lock")
try:
    job = orchestrator.run(job, unattended=args.unattended)
finally:
    lock.unlink(missing_ok=True)
```

Only added when the lock file exists (i.e., triggered by bot). If triggered from dashboard or CLI directly, lock file is absent and `unlink(missing_ok=True)` is a no-op.

---

## Systemd Unit

`deploy/nayzfreedom-bot.service`:
```ini
[Unit]
Description=NayzFreedom Telegram Bot
After=network.target

[Service]
Type=simple
User=nayzfreedom
WorkingDirectory=/opt/nayzfreedom
EnvironmentFile=/opt/nayzfreedom/.env
ExecStart=/opt/nayzfreedom/.venv/bin/python telegram_bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Testing (`tests/test_telegram_bot.py`)

| Test | Scenario |
|---|---|
| `test_status_idle` | `/status` when no lock → "No pipeline running" |
| `test_status_running` | `/status` with lock file present → "Pipeline running" |
| `test_cancel_clears_state` | `/cancel` mid-conversation → state reset, "Cancelled." |
| `test_full_conversation_flow` | Full happy path → pipeline spawned with correct args |
| `test_ignores_wrong_chat_id` | Message from other chat → no response |
| `test_pipeline_already_running` | Message when lock exists → "already running" message |
| `test_state_timeout` | State updated_at > 10 min ago → resets to idle |
| `test_stale_lock_cleared` | Lock file > 4 hours old → deleted, bot resumes |
| `test_confirm_start` | User taps Start → lock written, Popen called |
| `test_confirm_cancel` | User taps Cancel → state reset, no spawn |

---

## Out of Scope

- Webhook-based delivery (Phase 11c)
- Multi-user / role-based approval
- `/resume <job_id>` command (future)
- Group chat support
