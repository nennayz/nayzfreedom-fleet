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
