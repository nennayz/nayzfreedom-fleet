from __future__ import annotations
import logging
import time

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _api(token: str, method: str, **kwargs) -> dict:
    url = _BASE_URL.format(token=token, method=method)
    http_timeout = kwargs.get("timeout", 5) + 5
    try:
        resp = requests.post(url, json=kwargs, timeout=http_timeout)
        resp.raise_for_status()
    except Exception as exc:
        safe_url = _BASE_URL.format(token="<redacted>", method=method)
        raise type(exc)(f"{safe_url}: {exc}") from exc
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error ({method}): {data.get('description', 'unknown')}")
    return data


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
