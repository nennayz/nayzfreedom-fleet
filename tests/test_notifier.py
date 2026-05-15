from __future__ import annotations
from unittest.mock import patch, MagicMock

from notifier import send_slack_alert, send_weekly_report


FAILURES_ONE = [
    {"project": "nayzfreedom_fleet", "brief": "article_1", "content_type": "article", "exit_code": 1},
]
FAILURES_TIMEOUT = [
    {"project": "nayzfreedom_fleet", "brief": "short_video_1", "content_type": "video", "exit_code": None},
]
FAILURES_TWO = FAILURES_ONE + FAILURES_TIMEOUT


def test_send_slack_alert_dry_run_prints_message(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=True)
    out = capsys.readouterr().out
    assert "1/7 jobs failed" in out
    assert "nayzfreedom_fleet" in out
    assert "article_1" in out
    assert "article" in out
    assert "exit 1" in out


def test_send_slack_alert_posts_to_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_post = MagicMock()
    mock_post.return_value.__enter__ = lambda s: mock_post.return_value
    mock_post.return_value.__exit__ = MagicMock(return_value=False)
    mock_post.return_value.status_code = 200
    with patch("notifier.requests.post", mock_post):
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)
    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "https://hooks.slack.com/fake"
    assert "1/7 jobs failed" in mock_post.call_args.kwargs["json"]["text"]
    assert "nayzfreedom_fleet" in mock_post.call_args.kwargs["json"]["text"]


def test_send_slack_alert_missing_env_skips(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    mock_post = MagicMock()
    with patch("notifier.requests.post", mock_post):
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)
    mock_post.assert_not_called()


def test_send_slack_alert_non_2xx_does_not_raise(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: mock_resp
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.status_code = 500
    with patch("notifier.requests.post", return_value=mock_resp):
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)  # must not raise


def test_send_slack_alert_timeout_label_text(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    send_slack_alert(FAILURES_TIMEOUT, "2026-05-13", total=7, dry_run=True)
    out = capsys.readouterr().out
    assert "timeout" in out


def test_send_slack_alert_two_failures(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    send_slack_alert(FAILURES_TWO, "2026-05-13", total=7, dry_run=True)
    out = capsys.readouterr().out
    assert "2/7 jobs failed" in out
    assert "exit 1" in out
    assert "timeout" in out


def test_send_slack_alert_request_exception_does_not_raise(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    with patch("notifier.requests.post", side_effect=Exception("network error")):
        send_slack_alert(FAILURES_ONE, "2026-05-13", total=7, dry_run=False)  # must not raise


def test_send_weekly_report_dry_run_prints(capsys, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    send_weekly_report([":bar_chart: Weekly Report", "", "Facebook — 3 jobs"], dry_run=True)
    out = capsys.readouterr().out
    assert ":bar_chart: Weekly Report" in out
    assert "Facebook — 3 jobs" in out


def test_send_weekly_report_posts_to_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_post = MagicMock()
    mock_post.return_value.__enter__ = lambda s: mock_post.return_value
    mock_post.return_value.__exit__ = MagicMock(return_value=False)
    mock_post.return_value.status_code = 200
    with patch("notifier.requests.post", mock_post):
        send_weekly_report([":bar_chart: Weekly Report", "Facebook — 3 jobs"], dry_run=False)
    mock_post.assert_called_once()
    assert ":bar_chart: Weekly Report" in mock_post.call_args.kwargs["json"]["text"]


def test_send_weekly_report_missing_env_skips(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    mock_post = MagicMock()
    with patch("notifier.requests.post", mock_post):
        send_weekly_report([":bar_chart: Weekly Report"], dry_run=False)
    mock_post.assert_not_called()


def test_send_weekly_report_non_2xx_does_not_raise(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: mock_resp
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.status_code = 500
    with patch("notifier.requests.post", return_value=mock_resp):
        send_weekly_report([":bar_chart: Weekly Report"], dry_run=False)  # must not raise


def test_send_weekly_report_request_exception_does_not_raise(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    with patch("notifier.requests.post", side_effect=Exception("network error")):
        send_weekly_report([":bar_chart: Weekly Report"], dry_run=False)  # must not raise
