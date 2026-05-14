from __future__ import annotations
from unittest.mock import MagicMock, patch

from telegram_checkpoint import _drain_updates, send_and_wait


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
