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


def test_load_state_bad_updated_at(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"state": "awaiting_brief", "updated_at": None}))
    state = tb._load_state(path)  # should not raise
    assert state["state"] == "idle"
