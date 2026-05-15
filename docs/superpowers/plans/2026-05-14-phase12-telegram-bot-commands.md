# Phase 12: Telegram Bot Command Handler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the user to trigger pipeline runs from Telegram via a conversational bot (project → content type → dry run → brief → confirm) running as a persistent systemd service alongside the existing checkpoint flow.

**Architecture:** A new `telegram_bot.py` persistent service polls Telegram for commands when no pipeline is running. A shared lock file (`/tmp/nayz_pipeline.lock`) coordinates between the bot and the checkpoint system — the bot pauses when the lock exists and `send_and_wait()` writes the lock at every checkpoint so the bot never steals checkpoint responses regardless of how the pipeline was triggered.

**Tech Stack:** Python 3.12, `requests` (already in requirements.txt), `subprocess.Popen`, `pathlib.Path` for lock/state files, systemd.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `telegram_checkpoint.py` | Modify | Write lock file at start of `send_and_wait()` |
| `main.py` | Modify | Delete lock file in try/finally after `orchestrator.run()` |
| `telegram_bot.py` | Create | All bot logic: API helpers, state machine, poll loop |
| `tests/test_telegram_bot.py` | Create | 10 unit tests |
| `deploy/nayzfreedom-bot.service` | Create | systemd unit for bot service |
| `deploy/setup.sh` | Modify | Install + enable bot service |
| `deploy/update.sh` | Modify | Restart bot on update |

---

## Task 1: Lock file write in `telegram_checkpoint.py` and `main.py`

**Files:**
- Modify: `telegram_checkpoint.py` (lines 1–10, 77–96)
- Modify: `main.py` (lines 1–12, 130–140)
- Test: `tests/test_telegram_checkpoint.py` (add 2 tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_telegram_checkpoint.py`:

```python
def test_send_and_wait_writes_lock(tmp_path):
    import telegram_checkpoint as tc
    lock = tmp_path / "pipeline.lock"
    TOKEN, CHAT_ID = "tok", "456789"
    responses = [
        _resp([]),
        _resp({"message_id": 100}),
        _resp([{"update_id": 1, "message": {"chat": {"id": 456789}, "text": "approved"}}]),
        _resp({}),
    ]
    with patch("telegram_checkpoint.requests.post", side_effect=responses):
        with patch("telegram_checkpoint.time.monotonic", return_value=0.0):
            with patch.object(tc, "_LOCK_FILE", lock):
                send_and_wait("qa_review", "s", ["approved"], TOKEN, CHAT_ID, 30, "approved")
    # Lock is written (not deleted — main.py owns deletion)
    assert lock.exists()


def test_send_and_wait_writes_lock_on_send_failure(tmp_path):
    import telegram_checkpoint as tc
    lock = tmp_path / "pipeline.lock"
    call_n = 0

    def post_se(*args, **kwargs):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _resp([])
        raise Exception("send failed")

    with patch("telegram_checkpoint.requests.post", side_effect=post_se):
        with patch.object(tc, "_LOCK_FILE", lock):
            result = send_and_wait("qa_review", "s", ["approved"], "tok", "456", 30, "approved")
    assert result == "approved"
    # Lock is written even on failure (main.py will clean it up)
    assert lock.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack
python3 -m pytest tests/test_telegram_checkpoint.py::test_send_and_wait_writes_lock tests/test_telegram_checkpoint.py::test_send_and_wait_writes_lock_on_send_failure -v
```
Expected: FAIL with `AttributeError: module 'telegram_checkpoint' has no attribute '_LOCK_FILE'`

- [ ] **Step 3: Add `_LOCK_FILE` and lock write to `telegram_checkpoint.py`**

Add after the imports (after `import requests`, before `logger = ...`):

```python
from pathlib import Path

_LOCK_FILE = Path("/tmp/nayz_pipeline.lock")
```

Replace the start of `send_and_wait()` — the part before `keyboard = _build_keyboard(options)`:

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
    # Write lock so the bot service pauses during this checkpoint.
    # main.py owns deletion via try/finally.
    try:
        _LOCK_FILE.write_text(str(time.time()))
    except OSError as exc:
        logger.warning("Could not write pipeline lock file: %s", exc)

    keyboard = _build_keyboard(options)
    # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_telegram_checkpoint.py -v
```
Expected: all PASS (including 2 new ones)

- [ ] **Step 5: Add lock cleanup to `main.py`**

Add after the existing imports in `main.py`:

```python
from pathlib import Path

_LOCK_FILE = Path("/tmp/nayz_pipeline.lock")
```

Replace in `main()` (near line 130):
```python
# BEFORE:
result = orchestrator.run(job, unattended=args.unattended)

# AFTER:
try:
    result = orchestrator.run(job, unattended=args.unattended)
finally:
    _LOCK_FILE.unlink(missing_ok=True)
```

- [ ] **Step 6: Run full test suite to verify nothing broke**

```bash
python3 -m pytest tests/ --ignore=tests/test_dashboard.py -q
```
Expected: all pass, 1 warning

- [ ] **Step 7: Commit**

```bash
git add telegram_checkpoint.py main.py tests/test_telegram_checkpoint.py
git commit -m "feat: write pipeline lock file in send_and_wait, cleanup in main.py"
```

---

## Task 2: `telegram_bot.py` — API helpers and state management

**Files:**
- Create: `telegram_bot.py`
- Test: `tests/test_telegram_bot.py`

- [ ] **Step 1: Write failing tests for state helpers**

Create `tests/test_telegram_bot.py`:

```python
from __future__ import annotations
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import telegram_bot as tb

TOKEN = "test-token"
CHAT_ID = "123456"


def _resp(result_data):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"ok": True, "result": result_data}
    return m


def _msg_update(update_id: int, text: str, chat_id: str = CHAT_ID) -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": int(chat_id)}, "text": text},
    }


def _cb_update(update_id: int, data: str, chat_id: str = CHAT_ID) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cq{update_id}",
            "from": {"id": int(chat_id)},
            "message": {"chat": {"id": int(chat_id)}},
            "data": data,
        },
    }


def test_load_state_missing(tmp_path):
    state = tb._load_state(tmp_path / "state.json")
    assert state["state"] == "idle"


def test_load_state_expired(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "state": "awaiting_brief",
        "project": "slay_hack",
        "content_type": "video",
        "dry_run": False,
        "brief": None,
        "updated_at": time.time() - 700,  # 700s ago > 600s timeout
    }))
    state = tb._load_state(path)
    assert state["state"] == "idle"
    assert not path.exists()  # deleted


def test_load_state_valid(tmp_path):
    path = tmp_path / "state.json"
    data = {
        "state": "awaiting_brief",
        "project": "slay_hack",
        "content_type": "video",
        "dry_run": False,
        "brief": None,
        "updated_at": time.time(),
    }
    path.write_text(json.dumps(data))
    state = tb._load_state(path)
    assert state["state"] == "awaiting_brief"


def test_save_state_atomic(tmp_path):
    path = tmp_path / "state.json"
    data = {"state": "idle", "updated_at": 0.0}
    tb._save_state(path, data)
    assert json.loads(path.read_text())["state"] == "idle"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_telegram_bot.py::test_load_state_missing tests/test_telegram_bot.py::test_load_state_expired tests/test_telegram_bot.py::test_load_state_valid tests/test_telegram_bot.py::test_save_state_atomic -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'telegram_bot'`

- [ ] **Step 3: Create `telegram_bot.py` with helpers and state management**

Create `telegram_bot.py`:

```python
from __future__ import annotations
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"
_LOCK_FILE = Path("/tmp/nayz_pipeline.lock")
_STATE_FILE = Path("/tmp/nayz_bot_state.json")
_STATE_TIMEOUT = 600       # 10 minutes
_STALE_LOCK_AGE = 4 * 3600  # 4 hours
_CONTENT_TYPES = ["video", "article", "image", "infographic"]
_ROOT = Path(__file__).resolve().parent

_IDLE_STATE: dict = {
    "state": "idle",
    "project": None,
    "content_type": None,
    "dry_run": None,
    "brief": None,
    "updated_at": 0.0,
}


# ── Telegram API helpers ────────────────────────────────────────────────────

def _api(token: str, method: str, **kwargs) -> dict:
    url = _BASE_URL.format(token=token, method=method)
    http_timeout = kwargs.get("timeout", 5) + 5
    try:
        resp = requests.post(url, json=kwargs, timeout=http_timeout)
        resp.raise_for_status()
    except Exception as exc:
        safe_url = _BASE_URL.format(token="<redacted>", method=method)
        raise RuntimeError(
            f"Telegram request failed [{method}] {safe_url}: {type(exc).__name__}"
        ) from exc
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error ({method}): {data.get('description', 'unknown')}")
    return data


def _get_updates(token: str, offset: int, timeout: int = 5) -> list[dict]:
    try:
        data = _api(token, "getUpdates", offset=offset, timeout=timeout,
                    allowed_updates=["message", "callback_query"])
        return data.get("result", [])
    except Exception as exc:
        logger.warning("getUpdates failed: %s", exc)
        return []


def _send_message(token: str, chat_id: str, text: str, reply_markup=None) -> None:
    kwargs: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    try:
        _api(token, "sendMessage", **kwargs)
    except Exception as exc:
        logger.warning("sendMessage failed: %s", exc)


def _answer_callback(token: str, callback_query_id: str) -> None:
    try:
        _api(token, "answerCallbackQuery", callback_query_id=callback_query_id)
    except Exception as exc:
        logger.warning("answerCallbackQuery failed: %s", exc)


def _build_keyboard(options: list[str]) -> dict:
    return {"inline_keyboard": [[{"text": opt, "callback_data": opt}] for opt in options]}


# ── State management ────────────────────────────────────────────────────────

def _load_state(path: Path) -> dict:
    """Load conversation state. Returns idle state if missing or timed out."""
    if not path.exists():
        return dict(_IDLE_STATE)
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("updated_at", 0) > _STATE_TIMEOUT:
            path.unlink(missing_ok=True)
            return dict(_IDLE_STATE)
        return data
    except (json.JSONDecodeError, KeyError, OSError):
        return dict(_IDLE_STATE)


def _save_state(path: Path, state: dict) -> None:
    """Write state file atomically."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_telegram_bot.py::test_load_state_missing tests/test_telegram_bot.py::test_load_state_expired tests/test_telegram_bot.py::test_load_state_valid tests/test_telegram_bot.py::test_save_state_atomic -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add telegram_bot API helpers and state management"
```

---

## Task 3: `telegram_bot.py` — command handler (`_handle_update`)

**Files:**
- Modify: `telegram_bot.py` (append `_spawn_pipeline` and `_handle_update`)
- Modify: `tests/test_telegram_bot.py` (add 7 tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_telegram_bot.py`:

```python
def test_ignores_wrong_chat_id(tmp_path):
    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "lock"
    responses = []  # no API calls expected
    with patch("telegram_bot.requests.post", side_effect=responses):
        tb._handle_update(
            _msg_update(1, "hi", chat_id="999999"),
            TOKEN, CHAT_ID,
            root=tmp_path,
            state_file=state_file,
            lock_file=lock_file,
        )
    # No state written, no API called
    assert not state_file.exists()


def test_status_idle(tmp_path):
    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "lock"
    sent = []
    with patch("telegram_bot.requests.post", side_effect=lambda *a, **kw: (
        sent.append(kw), _resp({"message_id": 1})
    )[-1]):
        tb._handle_update(
            _msg_update(1, "/status"),
            TOKEN, CHAT_ID,
            root=tmp_path,
            state_file=state_file,
            lock_file=lock_file,
        )
    assert any("No pipeline running" in str(k) for k in sent)


def test_status_running(tmp_path):
    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "lock"
    lock_file.write_text(str(time.time()))
    sent = []
    with patch("telegram_bot.requests.post", side_effect=lambda *a, **kw: (
        sent.append(kw), _resp({"message_id": 1})
    )[-1]):
        tb._handle_update(
            _msg_update(1, "/status"),
            TOKEN, CHAT_ID,
            root=tmp_path,
            state_file=state_file,
            lock_file=lock_file,
        )
    assert any("already running" in str(k) or "running" in str(k).lower() for k in sent)


def test_cancel_clears_state(tmp_path):
    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "lock"
    tb._save_state(state_file, {
        "state": "awaiting_brief", "project": "slay_hack",
        "content_type": "video", "dry_run": False,
        "brief": None, "updated_at": time.time(),
    })
    sent = []
    with patch("telegram_bot.requests.post", side_effect=lambda *a, **kw: (
        sent.append(kw), _resp({"message_id": 1})
    )[-1]):
        tb._handle_update(
            _msg_update(1, "/cancel"),
            TOKEN, CHAT_ID,
            root=tmp_path,
            state_file=state_file,
            lock_file=lock_file,
        )
    assert not state_file.exists()
    assert any("Cancelled" in str(k) for k in sent)


def test_pipeline_already_running(tmp_path):
    lock_file = tmp_path / "lock"
    lock_file.write_text(str(time.time()))
    sent = []
    with patch("telegram_bot.requests.post", side_effect=lambda *a, **kw: (
        sent.append(kw), _resp({"message_id": 1})
    )[-1]):
        tb._handle_update(
            _msg_update(1, "hi"),
            TOKEN, CHAT_ID,
            root=tmp_path,
            state_file=tmp_path / "state.json",
            lock_file=lock_file,
        )
    assert any("already running" in str(k).lower() for k in sent)


def test_full_conversation_flow(tmp_path, monkeypatch):
    """Full happy path: idle → project → content_type → dry_run → brief → confirm → spawn."""
    # Create a fake project
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    (tmp_path / "projects" / "slay_hack" / "pm_profile.yaml").write_text("name: test")

    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "lock"

    spawned = []
    monkeypatch.setattr(tb.subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd))

    def fake_post(*args, **kwargs):
        return _resp({"message_id": 1})

    with patch("telegram_bot.requests.post", side_effect=fake_post):
        root = tmp_path

        def handle(text_or_data, is_cb=False):
            update = _cb_update(1, text_or_data) if is_cb else _msg_update(1, text_or_data)
            tb._handle_update(update, TOKEN, CHAT_ID, root=root,
                              state_file=state_file, lock_file=lock_file)

        handle("hi")                    # idle → awaiting_project
        handle("slay_hack", is_cb=True) # → awaiting_content_type
        handle("video", is_cb=True)     # → awaiting_dry_run
        handle("No — real run", is_cb=True)  # → awaiting_brief
        handle("skincare mistakes")     # → awaiting_confirm
        handle("Start ✅", is_cb=True)  # → spawn

    assert len(spawned) == 1
    cmd = spawned[0]
    assert "--project" in cmd and "slay_hack" in cmd
    assert "--brief" in cmd and "skincare mistakes" in cmd
    assert "--content-type" in cmd and "video" in cmd
    assert "--dry-run" not in cmd
    assert lock_file.exists()


def test_confirm_cancel(tmp_path, monkeypatch):
    (tmp_path / "projects" / "slay_hack").mkdir(parents=True)
    (tmp_path / "projects" / "slay_hack" / "pm_profile.yaml").write_text("name: test")

    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "lock"
    spawned = []
    monkeypatch.setattr(tb.subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd))

    with patch("telegram_bot.requests.post", return_value=_resp({"message_id": 1})):
        root = tmp_path

        def handle(text_or_data, is_cb=False):
            update = _cb_update(1, text_or_data) if is_cb else _msg_update(1, text_or_data)
            tb._handle_update(update, TOKEN, CHAT_ID, root=root,
                              state_file=state_file, lock_file=lock_file)

        handle("hi")
        handle("slay_hack", is_cb=True)
        handle("video", is_cb=True)
        handle("No — real run", is_cb=True)
        handle("skincare mistakes")
        handle("Cancel ❌", is_cb=True)

    assert spawned == []
    assert not state_file.exists()
    assert not lock_file.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_telegram_bot.py -k "ignores_wrong or status_idle or status_running or cancel_clears or already_running or full_conversation or confirm_cancel" -v
```
Expected: FAIL with `AttributeError: module 'telegram_bot' has no attribute '_handle_update'`

- [ ] **Step 3: Add `_spawn_pipeline` and `_handle_update` to `telegram_bot.py`**

Append to `telegram_bot.py`:

```python
# ── Pipeline spawn ──────────────────────────────────────────────────────────

def _spawn_pipeline(
    state: dict,
    token: str,
    chat_id: str,
    root: Path,
    lock_file: Path,
) -> None:
    cmd = [
        sys.executable, str(root / "main.py"),
        "--project", state["project"],
        "--brief", state["brief"],
        "--content-type", state["content_type"],
    ]
    if state.get("dry_run"):
        cmd.append("--dry-run")
    lock_file.write_text(str(time.time()))
    subprocess.Popen(cmd, cwd=str(root))
    _send_message(
        token, chat_id,
        "Pipeline started. ⏳\nYou'll receive checkpoint messages as it progresses.",
    )


# ── Conversation handler ────────────────────────────────────────────────────

def _handle_update(
    update: dict,
    token: str,
    chat_id: str,
    root: Path,
    state_file: Path = _STATE_FILE,
    lock_file: Path = _LOCK_FILE,
) -> None:
    """Process one Telegram update. Advances the conversation state machine."""
    # Extract sender and text/data
    if "callback_query" in update:
        cq = update["callback_query"]
        from_id = str(cq.get("from", {}).get("id", ""))
        text = cq.get("data", "").strip()
        callback_id = cq.get("id")
    elif "message" in update:
        msg = update["message"]
        from_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()
        callback_id = None
    else:
        return

    # Security: only respond to the authorised chat
    if from_id != str(chat_id):
        return

    if callback_id:
        _answer_callback(token, callback_id)

    # ── Commands (available in any state) ───────────────────────────────────
    if text == "/cancel":
        state_file.unlink(missing_ok=True)
        _send_message(token, chat_id, "Cancelled. ✋")
        return

    if text == "/status":
        if lock_file.exists():
            _send_message(token, chat_id,
                          "⏳ Pipeline is running. Wait for the next checkpoint.")
        else:
            _send_message(token, chat_id,
                          "✅ No pipeline running. Send any message to start.")
        return

    # Block new conversations while pipeline is running
    if lock_file.exists():
        _send_message(token, chat_id,
                      "⏳ Pipeline is already running. Wait for the next checkpoint.")
        return

    state = _load_state(state_file)
    current = state["state"]

    # ── State machine ───────────────────────────────────────────────────────
    if current == "idle":
        projects = sorted(p.parent.name for p in root.glob("projects/*/pm_profile.yaml"))
        if not projects:
            _send_message(token, chat_id, "❌ No projects found.")
            return
        keyboard = _build_keyboard(projects)
        _send_message(token, chat_id, "⚡ New pipeline run.\n\nWhich project?",
                      reply_markup=keyboard)
        _save_state(state_file, {**_IDLE_STATE, "state": "awaiting_project",
                                  "updated_at": time.time()})

    elif current == "awaiting_project":
        projects = sorted(p.parent.name for p in root.glob("projects/*/pm_profile.yaml"))
        if text not in projects:
            _send_message(token, chat_id, "Please pick a project:",
                          reply_markup=_build_keyboard(projects))
            return
        _save_state(state_file, {**state, "state": "awaiting_content_type",
                                  "project": text, "updated_at": time.time()})
        _send_message(token, chat_id, f"Project: <b>{text}</b>\n\nContent type?",
                      reply_markup=_build_keyboard(_CONTENT_TYPES))

    elif current == "awaiting_content_type":
        if text not in _CONTENT_TYPES:
            _send_message(token, chat_id, "Please pick a content type:",
                          reply_markup=_build_keyboard(_CONTENT_TYPES))
            return
        _save_state(state_file, {**state, "state": "awaiting_dry_run",
                                  "content_type": text, "updated_at": time.time()})
        _send_message(token, chat_id, "Dry run? (no API calls — for testing)",
                      reply_markup=_build_keyboard(["Yes — dry run", "No — real run"]))

    elif current == "awaiting_dry_run":
        if text == "Yes — dry run":
            dry = True
        elif text == "No — real run":
            dry = False
        else:
            _send_message(token, chat_id, "Please choose:",
                          reply_markup=_build_keyboard(["Yes — dry run", "No — real run"]))
            return
        _save_state(state_file, {**state, "state": "awaiting_brief",
                                  "dry_run": dry, "updated_at": time.time()})
        _send_message(token, chat_id, "Brief? Describe the content you want.")

    elif current == "awaiting_brief":
        if not text:
            _send_message(token, chat_id, "Please type your brief.")
            return
        _save_state(state_file, {**state, "state": "awaiting_confirm",
                                  "brief": text, "updated_at": time.time()})
        dry_label = "🔵 dry run" if state.get("dry_run") else "🔴 real run"
        summary = (
            f"Ready to start:\n"
            f"📁 {state['project']} | 🎬 {state['content_type']} | {dry_label}\n"
            f"📝 {text}\n\n"
            f"Start pipeline?"
        )
        _send_message(token, chat_id, summary,
                      reply_markup=_build_keyboard(["Start ✅", "Cancel ❌"]))

    elif current == "awaiting_confirm":
        if text == "Start ✅":
            _spawn_pipeline(state, token, chat_id, root, lock_file)
            state_file.unlink(missing_ok=True)
        elif text == "Cancel ❌":
            state_file.unlink(missing_ok=True)
            _send_message(token, chat_id, "Cancelled. ✋")
        else:
            _send_message(token, chat_id, "Start pipeline?",
                          reply_markup=_build_keyboard(["Start ✅", "Cancel ❌"]))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_telegram_bot.py -v
```
Expected: all 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add telegram_bot conversation handler and spawn logic"
```

---

## Task 4: `telegram_bot.py` — poll loop, stale lock, entry point

**Files:**
- Modify: `telegram_bot.py` (append `run_bot` + `__main__` block)
- Modify: `tests/test_telegram_bot.py` (add 2 tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_telegram_bot.py`:

```python
def test_stale_lock_cleared(tmp_path):
    """Lock older than 4 hours is deleted by run_bot on first iteration."""
    lock_file = tmp_path / "lock"
    lock_file.write_text(str(time.time() - 5 * 3600))  # 5 hours ago

    iterations = [0]

    def fake_get_updates(*args, **kwargs):
        iterations[0] += 1
        if iterations[0] >= 2:
            raise SystemExit(0)
        return []

    with patch.object(tb, "_get_updates", side_effect=fake_get_updates):
        with patch.object(tb, "_handle_update"):
            try:
                tb.run_bot(TOKEN, CHAT_ID, root=tmp_path,
                           lock_file=lock_file, state_file=tmp_path / "s.json")
            except SystemExit:
                pass

    assert not lock_file.exists()


def test_run_bot_pauses_when_lock_fresh(tmp_path):
    """Bot skips _handle_update when a fresh lock file exists."""
    lock_file = tmp_path / "lock"
    lock_file.write_text(str(time.time()))  # fresh lock

    iterations = [0]

    def fake_get_updates(*args, **kwargs):
        iterations[0] += 1
        if iterations[0] >= 2:
            raise SystemExit(0)
        return [_msg_update(1, "hi")]

    handled = []
    with patch.object(tb, "_get_updates", side_effect=fake_get_updates):
        with patch.object(tb, "_handle_update", side_effect=lambda *a, **kw: handled.append(1)):
            try:
                tb.run_bot(TOKEN, CHAT_ID, root=tmp_path,
                           lock_file=lock_file, state_file=tmp_path / "s.json")
            except SystemExit:
                pass

    assert handled == []  # _handle_update never called while lock is fresh
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_telegram_bot.py::test_stale_lock_cleared tests/test_telegram_bot.py::test_run_bot_pauses_when_lock_fresh -v
```
Expected: FAIL with `AttributeError: module 'telegram_bot' has no attribute 'run_bot'`

- [ ] **Step 3: Append `run_bot` and `__main__` block to `telegram_bot.py`**

```python
# ── Poll loop ───────────────────────────────────────────────────────────────

def run_bot(
    token: str,
    chat_id: str,
    root: Path,
    lock_file: Path = _LOCK_FILE,
    state_file: Path = _STATE_FILE,
) -> None:
    """Main entry point. Polls Telegram indefinitely. Blocks."""
    offset = 0
    logger.info("Telegram bot started (chat_id=%s).", chat_id)

    while True:
        if lock_file.exists():
            try:
                age = time.time() - float(lock_file.read_text())
                if age > _STALE_LOCK_AGE:
                    logger.warning("Stale lock file (%.0f s old) — removing.", age)
                    lock_file.unlink(missing_ok=True)
                else:
                    # Pipeline active — advance offset only, don't handle updates
                    updates = _get_updates(token, offset=offset, timeout=5)
                    for u in updates:
                        offset = u["update_id"] + 1
                    continue
            except (ValueError, OSError):
                lock_file.unlink(missing_ok=True)

        updates = _get_updates(token, offset=offset, timeout=5)
        for update in updates:
            offset = update["update_id"] + 1
            try:
                _handle_update(update, token, chat_id, root,
                               state_file=state_file, lock_file=lock_file)
            except Exception as exc:
                logger.error("Error handling update %s: %s",
                             update.get("update_id"), exc)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    _chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not _token or not _chat_id:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.")
        sys.exit(1)
    run_bot(_token, _chat_id, root=_ROOT)
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
python3 -m pytest tests/test_telegram_bot.py -v
```
Expected: all 13 tests PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest tests/ --ignore=tests/test_dashboard.py -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add telegram_bot poll loop and entry point"
```

---

## Task 5: systemd unit and deploy scripts

**Files:**
- Create: `deploy/nayzfreedom-bot.service`
- Modify: `deploy/setup.sh`
- Modify: `deploy/update.sh`

- [ ] **Step 1: Create `deploy/nayzfreedom-bot.service`**

```ini
[Unit]
Description=NayzFreedom Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=nayzfreedom
WorkingDirectory=/opt/nayzfreedom
EnvironmentFile=/opt/nayzfreedom/.env
ExecStart=/opt/nayzfreedom/.venv/bin/python telegram_bot.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Update `deploy/setup.sh` — add bot service installation**

In `setup.sh`, find the loop that copies service files and add `nayzfreedom-bot.service`:

```bash
for unit in \
    nayzfreedom-dashboard.service \
    nayzfreedom-bot.service \
    nayzfreedom-scheduler.service \
    nayzfreedom-scheduler.timer \
    nayzfreedom-reporter.service \
    nayzfreedom-reporter.timer; do
    cp "$DEPLOY_DIR/$unit" "/etc/systemd/system/$unit"
done
```

Also add after `systemctl enable --now nayzfreedom-dashboard.service`:

```bash
systemctl enable --now nayzfreedom-bot.service
```

And add to the "Next steps" echo at the end:
```bash
echo "  Bot logs:         journalctl -u nayzfreedom-bot -f"
```

- [ ] **Step 3: Update `deploy/update.sh` — restart bot**

After `systemctl restart nayzfreedom-dashboard.service`, add:

```bash
systemctl restart nayzfreedom-bot.service
systemctl status nayzfreedom-bot.service --no-pager
```

- [ ] **Step 4: Run full test suite one last time**

```bash
python3 -m pytest tests/ --ignore=tests/test_dashboard.py -q
```
Expected: all pass

- [ ] **Step 5: Commit and push**

```bash
git add telegram_bot.py tests/test_telegram_bot.py telegram_checkpoint.py main.py \
    deploy/nayzfreedom-bot.service deploy/setup.sh deploy/update.sh
git commit -m "feat: Phase 12 — Telegram bot command handler complete"
git push origin main
```

- [ ] **Step 6: Deploy to VPS**

In the Hostinger terminal:

```bash
cd /opt/nayzfreedom && git pull
cp deploy/nayzfreedom-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now nayzfreedom-bot.service
systemctl status nayzfreedom-bot.service --no-pager
```

Expected output: `Active: active (running)`

- [ ] **Step 7: Smoke test on Telegram**

Send any message to the bot → should reply "⚡ New pipeline run. Which project?" with a button for `slay_hack`.

Send `/status` → should reply "✅ No pipeline running."
