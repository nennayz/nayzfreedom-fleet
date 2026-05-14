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
