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


def test_full_conversation_flow_dry_run(tmp_path, monkeypatch):
    """Dry-run path: Start ✅ should include --dry-run in spawned command."""
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
        handle("Yes — dry run", is_cb=True)   # ← dry run selected
        handle("skincare mistakes")
        handle("Start ✅", is_cb=True)

    assert len(spawned) == 1
    cmd = spawned[0]
    assert "--dry-run" in cmd


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
