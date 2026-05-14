# Phase 11b: Telegram Checkpoint Approval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terminal `input()` prompt at pipeline checkpoints with Telegram inline-keyboard + free-text messages, auto-approving on timeout.

**Architecture:** A new `telegram_checkpoint.py` module wraps the Telegram Bot API using `requests` (already a dependency). `checkpoint.py` reads three env vars at module level and delegates `pause()` to Telegram when both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set and `unattended=False`. On timeout it falls back to the same decisions as `--unattended` mode.

**Tech Stack:** Python `requests`, Telegram Bot API (`getUpdates` long-polling, `sendMessage`, `editMessageText`, `answerCallbackQuery`).

---

## File Map

| File | Action | What changes |
|---|---|---|
| `telegram_checkpoint.py` | **Create** | All Telegram HTTP helpers + `send_and_wait()` |
| `checkpoint.py` | **Modify** | Read env vars at module level, `import telegram_checkpoint`, delegate in `pause()` |
| `tests/test_telegram_checkpoint.py` | **Create** | 8 tests for drain + `send_and_wait()` |
| `tests/test_checkpoint.py` | **Modify** | 3 new tests at bottom of existing file |
| `.env.example` | **Modify** | Add 3 new vars |
| `CLAUDE.md` | **Modify** | Add Telegram setup instructions |

---

## Task 1: `telegram_checkpoint.py` — helpers + drain tests

**Files:**
- Create: `telegram_checkpoint.py`
- Create: `tests/test_telegram_checkpoint.py`

- [ ] **Step 1: Write 2 failing tests for `_drain_updates`**

Create `tests/test_telegram_checkpoint.py`:

```python
from __future__ import annotations
from unittest.mock import MagicMock, patch

from telegram_checkpoint import _drain_updates


def _resp(result_data):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"ok": True, "result": result_data}
    return m


def test_drain_stale_updates_empty():
    with patch("telegram_checkpoint.requests.post", return_value=_resp([])):
        result = _drain_updates("token123")
    assert result == 0


def test_drain_stale_updates_has_updates():
    updates = [{"update_id": 10}, {"update_id": 20}]
    with patch("telegram_checkpoint.requests.post", return_value=_resp(updates)):
        result = _drain_updates("token123")
    assert result == 21
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_telegram_checkpoint.py -v
```

Expected: `ImportError` (module doesn't exist yet).

- [ ] **Step 3: Create `telegram_checkpoint.py` with all helpers (stub `send_and_wait`)**

```python
from __future__ import annotations
import logging
import time

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _api(token: str, method: str, **kwargs) -> dict:
    url = _BASE_URL.format(token=token, method=method)
    resp = requests.post(url, json=kwargs, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_updates(token: str, offset: int, timeout: int = 5) -> list[dict]:
    try:
        data = _api(
            token, "getUpdates",
            offset=offset, timeout=timeout,
            allowed_updates=["message", "callback_query"],
        )
        return data.get("result", [])
    except Exception as exc:
        logger.warning("getUpdates failed: %s", exc)
        return []


def _drain_updates(token: str) -> int:
    updates = _get_updates(token, offset=-1, timeout=0)
    if updates:
        return updates[-1]["update_id"] + 1
    return 0


def _send_message(token: str, chat_id: str, text: str, reply_markup=None) -> int:
    kwargs: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    data = _api(token, "sendMessage", **kwargs)
    return data["result"]["message_id"]


def _edit_message(token: str, chat_id: str, message_id: int, text: str) -> None:
    try:
        _api(
            token, "editMessageText",
            chat_id=chat_id, message_id=message_id, text=text,
            parse_mode="HTML", reply_markup={"inline_keyboard": []},
        )
    except Exception as exc:
        logger.warning("editMessageText failed: %s", exc)


def _answer_callback(token: str, callback_query_id: str) -> None:
    try:
        _api(token, "answerCallbackQuery", callback_query_id=callback_query_id)
    except Exception as exc:
        logger.warning("answerCallbackQuery failed: %s", exc)


def _build_keyboard(options: list[str]) -> dict:
    return {"inline_keyboard": [[{"text": opt, "callback_data": opt}] for opt in options]}


def send_and_wait(
    stage: str,
    summary: str,
    options: list[str],
    token: str,
    chat_id: str,
    timeout_seconds: int,
    fallback: str,
) -> str:
    raise NotImplementedError("implemented in Task 2")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_telegram_checkpoint.py -v
```

Expected: `test_drain_stale_updates_empty PASSED`, `test_drain_stale_updates_has_updates PASSED`.

- [ ] **Step 5: Commit**

```bash
git add telegram_checkpoint.py tests/test_telegram_checkpoint.py
git commit -m "feat: add telegram_checkpoint helpers and drain tests"
```

---

## Task 2: `send_and_wait()` — happy paths (button press + text reply)

**Files:**
- Modify: `telegram_checkpoint.py` (replace stub with full implementation)
- Modify: `tests/test_telegram_checkpoint.py` (add 2 tests)

- [ ] **Step 1: Add 2 failing tests for happy paths**

First, update the existing import at line 4 of `tests/test_telegram_checkpoint.py` (replace the `_drain_updates`-only import):

```python
from telegram_checkpoint import _drain_updates, send_and_wait
```

Then append these two test functions to the bottom of the file:

```python
def test_send_and_wait_button_press():
    TOKEN, CHAT_ID = "tok", "456789"
    responses = [
        _resp([]),                          # drain getUpdates
        _resp({"message_id": 100}),         # sendMessage (checkpoint)
        _resp([{                            # getUpdates (poll) → callback query
            "update_id": 1,
            "callback_query": {
                "id": "cq1",
                "from": {"id": 456789},
                "message": {"chat": {"id": 456789}},
                "data": "approved",
            },
        }]),
        _resp(True),                        # answerCallbackQuery
        _resp({}),                          # editMessageText
    ]
    with patch("telegram_checkpoint.requests.post", side_effect=responses):
        with patch("telegram_checkpoint.time.monotonic", return_value=0.0):
            result = send_and_wait(
                "content_review", "Script ok.", ["approved", "rejected"],
                TOKEN, CHAT_ID, 30, "approved",
            )
    assert result == "approved"


def test_send_and_wait_text_reply():
    TOKEN, CHAT_ID = "tok", "456789"
    responses = [
        _resp([]),                          # drain
        _resp({"message_id": 100}),         # sendMessage
        _resp([{                            # getUpdates (poll) → text message
            "update_id": 1,
            "message": {"chat": {"id": 456789}, "text": "2"},
        }]),
        _resp({}),                          # editMessageText
    ]
    with patch("telegram_checkpoint.requests.post", side_effect=responses):
        with patch("telegram_checkpoint.time.monotonic", return_value=0.0):
            result = send_and_wait(
                "idea_selection", "Pick one.", ["1", "2", "3"],
                TOKEN, CHAT_ID, 30, "1",
            )
    assert result == "2"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_telegram_checkpoint.py::test_send_and_wait_button_press tests/test_telegram_checkpoint.py::test_send_and_wait_text_reply -v
```

Expected: `NotImplementedError`.

- [ ] **Step 3: Replace the stub `send_and_wait` with the full implementation**

Replace the `send_and_wait` function at the bottom of `telegram_checkpoint.py`:

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
    keyboard = _build_keyboard(options)
    text = f"⏸ <b>Checkpoint: {stage}</b>\n\n{summary}\n\nReply with a button or type freely:"

    offset = _drain_updates(token)

    try:
        message_id = _send_message(token, chat_id, text, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Failed to send Telegram checkpoint message: %s", exc)
        return fallback

    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        poll_timeout = min(5, int(remaining))
        if poll_timeout <= 0:
            break

        updates = _get_updates(token, offset=offset, timeout=poll_timeout)
        for update in updates:
            offset = update["update_id"] + 1

            if "callback_query" in update:
                cq = update["callback_query"]
                cq_chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
                if cq_chat_id != str(chat_id):
                    continue
                decision = cq["data"]
                _answer_callback(token, cq["id"])
                _edit_message(token, chat_id, message_id,
                               text + f"\n✅ Decision recorded: {decision}")
                return decision

            elif "message" in update:
                msg = update["message"]
                msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                if msg_chat_id != str(chat_id):
                    continue
                decision = msg.get("text", "").strip()
                _edit_message(token, chat_id, message_id,
                               text + f"\n✅ Decision recorded: {decision}")
                return decision

    logger.warning(
        "Telegram checkpoint %s timed out after %ds, using fallback: %s",
        stage, timeout_seconds, fallback,
    )
    try:
        _send_message(
            token, chat_id,
            f"⏰ No reply for <b>{stage}</b> — auto-continuing with: {fallback}",
        )
    except Exception:
        pass
    return fallback
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_telegram_checkpoint.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add telegram_checkpoint.py tests/test_telegram_checkpoint.py
git commit -m "feat: implement send_and_wait with button press and text reply"
```

---

## Task 3: `send_and_wait()` — edge cases

**Files:**
- Modify: `tests/test_telegram_checkpoint.py` (add 4 tests — no code changes needed if Task 2 implementation is correct)

- [ ] **Step 1: Add 4 failing edge case tests**

Append to `tests/test_telegram_checkpoint.py`:

```python
def test_send_and_wait_ignores_other_chat():
    TOKEN, CHAT_ID = "tok", "456789"
    responses = [
        _resp([]),                          # drain
        _resp({"message_id": 100}),         # sendMessage
        _resp([{                            # poll 1: wrong chat
            "update_id": 1,
            "message": {"chat": {"id": 999999}, "text": "hacked"},
        }]),
        _resp([{                            # poll 2: correct chat
            "update_id": 2,
            "message": {"chat": {"id": 456789}, "text": "approved"},
        }]),
        _resp({}),                          # editMessageText
    ]
    with patch("telegram_checkpoint.requests.post", side_effect=responses):
        with patch("telegram_checkpoint.time.monotonic", return_value=0.0):
            result = send_and_wait(
                "qa_review", "s", ["approved", "rejected"],
                TOKEN, CHAT_ID, 30, "approved",
            )
    assert result == "approved"


def test_send_and_wait_timeout():
    TOKEN, CHAT_ID = "tok", "456789"
    responses = [
        _resp([]),                          # drain
        _resp({"message_id": 100}),         # sendMessage (checkpoint)
        _resp({"message_id": 101}),         # sendMessage (timeout notification)
    ]
    with patch("telegram_checkpoint.requests.post", side_effect=responses):
        # monotonic call 1 → 0.0 (deadline = 30); call 2 → 100.0 (while False, skip loop)
        with patch("telegram_checkpoint.time.monotonic", side_effect=[0.0, 100.0]):
            result = send_and_wait(
                "final_approval", "Last check.", ["approved", "rejected"],
                TOKEN, CHAT_ID, 30, "approved",
            )
    assert result == "approved"


def test_send_and_wait_send_fails():
    call_n = 0

    def post_se(*args, **kwargs):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _resp([])            # drain succeeds
        raise Exception("send failed")  # sendMessage raises

    with patch("telegram_checkpoint.requests.post", side_effect=post_se):
        result = send_and_wait(
            "qa_review", "s", ["approved"], "tok", "456", 30, "approved",
        )
    assert result == "approved"


def test_send_and_wait_get_updates_error():
    call_n = 0

    def post_se(*args, **kwargs):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _resp([])                    # drain
        if call_n == 2:
            return _resp({"message_id": 100})   # sendMessage
        if call_n == 3:
            raise Exception("network error")    # getUpdates in loop raises
        return _resp({"message_id": 101})       # timeout notification

    with patch("telegram_checkpoint.requests.post", side_effect=post_se):
        # monotonic: deadline=0+30=30; while 0<30→True; remaining=30-0=30;
        # getUpdates raises (caught); while 100<30→False; timeout handler
        with patch("telegram_checkpoint.time.monotonic",
                   side_effect=[0.0, 0.0, 0.0, 100.0]):
            result = send_and_wait(
                "qa_review", "s", ["approved"], "tok", "456", 30, "approved",
            )
    assert result == "approved"
```

- [ ] **Step 2: Run to verify all 4 fail (or verify existing implementation handles them)**

```bash
pytest tests/test_telegram_checkpoint.py::test_send_and_wait_ignores_other_chat tests/test_telegram_checkpoint.py::test_send_and_wait_timeout tests/test_telegram_checkpoint.py::test_send_and_wait_send_fails tests/test_telegram_checkpoint.py::test_send_and_wait_get_updates_error -v
```

Expected: all 4 PASS (the Task 2 implementation already handles all these paths). If any fail, fix the edge case in `telegram_checkpoint.py`.

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all existing tests still pass, 8 new tests in `test_telegram_checkpoint.py` pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_telegram_checkpoint.py
git commit -m "test: add edge case tests for send_and_wait"
```

---

## Task 4: Modify `checkpoint.py` to delegate to Telegram

**Files:**
- Modify: `checkpoint.py`
- Modify: `tests/test_checkpoint.py` (append 3 tests)

- [ ] **Step 1: Add 3 failing tests to `tests/test_checkpoint.py`**

Append to the **bottom** of the existing `tests/test_checkpoint.py` (keep all existing tests untouched):

```python
from unittest.mock import MagicMock


def test_pause_uses_telegram_when_env_set(monkeypatch):
    import checkpoint as cp
    monkeypatch.setattr(cp, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(cp, "TELEGRAM_CHAT_ID", "123456")
    monkeypatch.setattr(cp, "TELEGRAM_TIMEOUT_MINUTES", 30)

    mock_send = MagicMock(return_value="approved")
    monkeypatch.setattr(cp.telegram_checkpoint, "send_and_wait", mock_send)

    job = make_job()
    result = cp.pause("content_review", "Script ok.", ["approved", "rejected"], job)

    mock_send.assert_called_once_with(
        stage="content_review",
        summary="Script ok.",
        options=["approved", "rejected"],
        token="test-token",
        chat_id="123456",
        timeout_seconds=1800,
        fallback="approved",
    )
    assert result.decision == "approved"
    assert result.stage == "content_review"


def test_pause_falls_back_to_input_when_no_token(monkeypatch):
    import checkpoint as cp
    monkeypatch.setattr(cp, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(cp, "TELEGRAM_CHAT_ID", "")

    with patch("builtins.input", return_value="1"):
        result = cp.pause("idea_selection", "Pick an idea.", ["Idea A", "Idea B"], make_job())

    assert result.decision == "1"


def test_pause_skips_telegram_when_unattended(monkeypatch):
    import checkpoint as cp
    monkeypatch.setattr(cp, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(cp, "TELEGRAM_CHAT_ID", "123456")

    mock_send = MagicMock()
    monkeypatch.setattr(cp.telegram_checkpoint, "send_and_wait", mock_send)

    result = cp.pause("qa_review", "summary", [], make_job(), unattended=True)

    mock_send.assert_not_called()
    assert result.decision == "approved"
```

Note: `make_job()` and `patch` are already imported at the top of the existing file. The new tests use them without additional imports.

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_checkpoint.py::test_pause_uses_telegram_when_env_set tests/test_checkpoint.py::test_pause_falls_back_to_input_when_no_token tests/test_checkpoint.py::test_pause_skips_telegram_when_unattended -v
```

Expected: `AttributeError: module 'checkpoint' has no attribute 'telegram_checkpoint'` (or similar — the module-level import doesn't exist yet).

- [ ] **Step 3: Rewrite `checkpoint.py` to add env vars + Telegram delegation**

Replace the entire file:

```python
from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from datetime import datetime

from models.content_job import ContentJob, CheckpointDecision

import telegram_checkpoint

logger = logging.getLogger(__name__)

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

_UNATTENDED_DECISIONS: dict[str, str] = {
    "idea_selection": "1",
    "content_review": "approved",
    "qa_review": "approved",
    "final_approval": "approved",
}


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
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  [{i}] {opt}")
        print()
        decision = input("Your choice (or type freely): ").strip()
    else:
        decision = _UNATTENDED_DECISIONS.get(stage, "approved")
        print(f"  [unattended] auto-decision: {decision}")

    job.checkpoint_log.append(
        CheckpointDecision(stage=stage, decision=decision, timestamp=datetime.now())
    )
    return CheckpointResult(stage=stage, decision=decision)
```

- [ ] **Step 4: Run all checkpoint tests to verify they pass**

```bash
pytest tests/test_checkpoint.py -v
```

Expected: all 10 tests pass (7 existing + 3 new).

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add checkpoint.py tests/test_checkpoint.py
git commit -m "feat: integrate Telegram checkpoint approval in checkpoint.py"
```

---

## Task 5: Update `.env.example` and `CLAUDE.md`

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add Telegram vars to `.env.example`**

Append to `.env.example` after `DASHBOARD_PASSWORD=`:

```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_TIMEOUT_MINUTES=30
```

- [ ] **Step 2: Add Telegram setup section to `CLAUDE.md`**

In `CLAUDE.md`, append the following block after the `python dashboard.py --host 0.0.0.0 --port 8000` line:

```bash
# Telegram checkpoint approval (Phase 11b)
# 1. Create a bot: message @BotFather on Telegram → /newbot → copy token
# 2. Get your chat ID: message @userinfobot on Telegram → copy the id number
# 3. Set env vars in .env:
#    TELEGRAM_BOT_TOKEN=<token>
#    TELEGRAM_CHAT_ID=<your_id>
#    TELEGRAM_TIMEOUT_MINUTES=30   # optional, default 30
# 4. Run pipeline in attended mode (no --unattended flag):
#    python main.py --project slay_hack --brief "..."
#    Pipeline pauses at each checkpoint and sends a Telegram message.
#    Reply via button or free text. Auto-approves after TELEGRAM_TIMEOUT_MINUTES if no reply.
```

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add .env.example CLAUDE.md
git commit -m "docs: add Telegram checkpoint env vars and setup notes"
```
