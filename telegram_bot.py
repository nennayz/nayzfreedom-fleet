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
    except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
        return dict(_IDLE_STATE)


def _save_state(path: Path, state: dict) -> None:
    """Write state file atomically."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state))
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


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
    try:
        subprocess.Popen(cmd, cwd=str(root))
    except Exception:
        lock_file.unlink(missing_ok=True)
        raise
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
        if callback_id:
            _send_message(token, chat_id, "Please type your brief as a message.")
            return
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
