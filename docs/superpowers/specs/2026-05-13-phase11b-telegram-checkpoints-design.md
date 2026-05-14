# Phase 11b: Telegram Checkpoint Approval — Design Spec

**Date:** 2026-05-13
**Phase:** 11b
**Status:** Approved

---

## Goal

Replace the terminal `input()` prompt at pipeline checkpoints with Telegram messages. The pipeline pauses, sends a message with inline keyboard buttons, and waits for either a button press or a free-text reply. On timeout, it auto-continues using the same decisions as `--unattended` mode.

---

## Scope

- `telegram_checkpoint.py` — new file, `send_and_wait()` + private HTTP helpers
- `checkpoint.py` — modified to delegate to Telegram when env vars are set
- `.env.example` — 3 new vars
- `CLAUDE.md` — setup notes
- `requirements.txt` — no change (`requests` already present)
- Phase 11c (multi-user, roles, webhook) is explicitly out of scope

---

## File Structure

```
telegram_checkpoint.py        ← new
checkpoint.py                 ← modified
tests/
  test_telegram_checkpoint.py ← new
  test_checkpoint.py          ← modified (3 new tests)
```

---

## Environment Variables

```
TELEGRAM_BOT_TOKEN=        # from @BotFather
TELEGRAM_CHAT_ID=          # your personal chat ID (get from @userinfobot)
TELEGRAM_TIMEOUT_MINUTES=30
```

`checkpoint.py` reads all three at module level. If only one of `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` is set (both required together), logs a warning at import time and falls back to `input()`. Pipeline still works without Telegram.

---

## `telegram_checkpoint.py`

One public function:

```python
def send_and_wait(
    stage: str,
    summary: str,
    options: list[str],
    token: str,
    chat_id: str,
    timeout_seconds: int,
    fallback: str,
) -> str:
```

### Private helpers

```python
def _api(token: str, method: str, **kwargs) -> dict:
    """POST to Telegram Bot API. Raises on HTTP error."""

def _get_updates(token: str, offset: int, timeout: int = 5) -> list[dict]:
    """Long-poll getUpdates. Returns [] on error (logs warning, never raises)."""

def _drain_updates(token: str) -> int:
    """Calls getUpdates with timeout=0 to get current offset. Returns next offset."""

def _send_message(token: str, chat_id: str, text: str, reply_markup=None) -> int:
    """Sends message, returns message_id."""

def _edit_message(token: str, chat_id: str, message_id: int, text: str) -> None:
    """Edits message text and removes inline keyboard. Silently ignores errors."""

def _answer_callback(token: str, callback_query_id: str) -> None:
    """Answers callback query to clear loading state. Silently ignores errors."""

def _build_keyboard(options: list[str]) -> dict:
    """Returns Telegram inline_keyboard dict. One button per row."""
```

### `send_and_wait()` flow

1. Build inline keyboard from `options`
2. Drain stale updates → get `offset` (before sending, so no fast reply is missed)
3. Send message to `chat_id`:
   ```
   ⏸ Checkpoint: {stage}

   {summary}

   Reply with a button or type freely:
   [option1]  [option2]  ...
   ```
4. Set `deadline = now + timeout_seconds` (countdown starts after send, giving the user the full window)
5. Poll loop until deadline:
   - `getUpdates(offset=offset, timeout=min(5, remaining))`
   - For each update, advance `offset`
   - Skip updates not from `chat_id`
   - **Callback query** (button press): answer callback, edit message to remove buttons + append `✅ Decision recorded: {data}`, return `callback_data`
   - **Text message**: edit message to append `✅ Decision recorded: {text}`, return `text`
   - `getUpdates` errors: log warning, continue loop
6. On timeout:
   - Log warning
   - Send: `⏰ No reply for {stage} — auto-continuing with: {fallback}`
   - Return `fallback`
7. If initial `sendMessage` fails: log error, return `fallback` immediately

Security: updates from any chat other than `chat_id` are silently skipped.

---

## `checkpoint.py` changes

Read at module level:

```python
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
try:
    TELEGRAM_TIMEOUT_MINUTES = int(os.environ.get("TELEGRAM_TIMEOUT_MINUTES", "30"))
except ValueError:
    logger.warning("Invalid TELEGRAM_TIMEOUT_MINUTES, defaulting to 30")
    TELEGRAM_TIMEOUT_MINUTES = 30

if bool(TELEGRAM_BOT_TOKEN) != bool(TELEGRAM_CHAT_ID):
    logger.warning(
        "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set. "
        "Telegram checkpoints disabled — falling back to input()."
    )
```

Import at top level for test patching:

```python
import telegram_checkpoint
```

Modified `pause()`:

```python
def pause(stage, summary, options, job, unattended=False) -> CheckpointResult:
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and not unattended:
        decision = telegram_checkpoint.send_and_wait(
            stage=stage,
            summary=summary,
            options=options,
            token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
            timeout_seconds=TELEGRAM_TIMEOUT_MINUTES * 60,
            fallback=_UNATTENDED_DECISIONS.get(stage, "approved"),
        )
    elif not unattended:
        decision = input("Your choice (or type freely): ").strip()
    else:
        decision = _UNATTENDED_DECISIONS.get(stage, "approved")

    job.checkpoint_log.append(CheckpointDecision(stage=stage, decision=decision, timestamp=datetime.now()))
    return CheckpointResult(stage=stage, decision=decision)
```

---

## Message Format

### Idea selection checkpoint

```
⏸ Checkpoint: idea_selection

[summary with Zoe's ideas]

Reply with a button or type freely:
[1]
[2]
[3]
[4]
[5]
```

### Approve/reject checkpoints (`content_review`, `qa_review`, `final_approval`)

```
⏸ Checkpoint: content_review

[summary from pipeline]

Reply with a button or type freely:
[approved]
[rejected]
```

After decision received (edit in place):

```
⏸ Checkpoint: content_review

[summary]

Reply with a button or type freely:
✅ Decision recorded: approved
```

On timeout:

```
⏰ No reply for content_review — auto-continuing with: approved
```

---

## Polling Mechanism

- `getUpdates` with `timeout=5` (long polling, 5s per request)
- `offset` starts from `_drain_updates()` result — skips all pre-existing messages
- Each iteration: `poll_timeout = min(5, int(deadline - now))`; break when `poll_timeout <= 0`
- `getUpdates` network errors: log warning, continue loop (do not abort)
- Only `sendMessage` failure aborts early (returns fallback)

---

## Timeout & Fallback

- Default: 30 minutes (`TELEGRAM_TIMEOUT_MINUTES=30`)
- Fallback decisions (same as `--unattended` mode):

| Stage | Fallback |
|---|---|
| `idea_selection` | `"1"` |
| `content_review` | `"approved"` |
| `qa_review` | `"approved"` |
| `final_approval` | `"approved"` |

---

## Testing

### `tests/test_telegram_checkpoint.py`

All tests mock `requests.post`.

| Test | Scenario |
|---|---|
| `test_send_and_wait_button_press` | Callback query from correct chat → returns `callback_data`, answers callback, edits message |
| `test_send_and_wait_text_reply` | Text message from correct chat → returns text, edits message |
| `test_send_and_wait_ignores_other_chat` | Update from wrong chat_id → skipped; second update from correct chat → returned |
| `test_send_and_wait_timeout` | No updates until deadline → returns fallback, sends timeout notification |
| `test_send_and_wait_send_fails` | `sendMessage` raises → returns fallback immediately |
| `test_send_and_wait_get_updates_error` | `getUpdates` raises → logs warning, loop continues |
| `test_drain_stale_updates_empty` | No existing updates → returns 0 |
| `test_drain_stale_updates_has_updates` | Existing updates → returns last update_id + 1 |

### `tests/test_checkpoint.py` additions

| Test | Scenario |
|---|---|
| `test_pause_uses_telegram_when_env_set` | Monkeypatch both env vars, mock `telegram_checkpoint.send_and_wait` → called with correct args |
| `test_pause_falls_back_to_input_when_no_token` | No env vars → `input()` called |
| `test_pause_skips_telegram_when_unattended` | Env vars set but `unattended=True` → `send_and_wait` not called |

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Only one of `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` set | Warning at import, fallback to `input()` |
| `sendMessage` fails | Log error, return fallback, pipeline continues |
| `getUpdates` network error | Log warning, continue poll loop |
| Telegram 5xx during poll | Treated same as network error |
| Reply from unknown chat | Silently skipped |
| Timeout | Log warning, send notification, return fallback |

---

## Setup Notes (for CLAUDE.md)

```
# Telegram checkpoint approval (Phase 11b)
# 1. Create a bot: message @BotFather on Telegram → /newbot → copy token
# 2. Get your chat ID: message @userinfobot → copy the id number
# 3. Set env vars in .env:
#    TELEGRAM_BOT_TOKEN=<token>
#    TELEGRAM_CHAT_ID=<your_id>
#    TELEGRAM_TIMEOUT_MINUTES=30   # optional, default 30
# 4. Start a pipeline (attended mode, no --unattended flag)
#    The pipeline will pause at each checkpoint and send you a Telegram message
```

---

## Out of Scope

- Multi-user approval (roles, delegation)
- Webhook-based delivery (requires public HTTPS endpoint)
- Approving from groups or channels (only direct bot chat)
- Cancelling a running job via Telegram
- Phase 11c features
