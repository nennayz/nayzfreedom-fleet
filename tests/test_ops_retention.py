from __future__ import annotations

import json

from ops_retention import rotate_ops_log


def test_rotate_ops_log_archives_and_keeps_recent_lines(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "ops_actions.jsonl"
    lines = [
        json.dumps({"timestamp": f"2026-05-16T00:00:0{i}Z", "action": f"a{i}"})
        for i in range(6)
    ]
    log_path.write_text("\n".join(lines) + "\n")

    result = rotate_ops_log(tmp_path, max_bytes=10, keep_lines=2)

    assert result["rotated"] is True
    assert result["kept_lines"] == 2
    assert log_path.read_text().splitlines() == lines[-2:]
    archives = list((log_dir / "archive").glob("ops_actions-*.jsonl"))
    assert len(archives) == 1
    assert archives[0].read_text().splitlines() == lines


def test_rotate_ops_log_skips_small_or_missing_logs(tmp_path):
    missing = rotate_ops_log(tmp_path, max_bytes=10, keep_lines=2)
    assert missing["rotated"] is False
    assert missing["reason"] == "missing"

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "ops_actions.jsonl").write_text("{}\n")

    small = rotate_ops_log(tmp_path, max_bytes=100, keep_lines=2)
    assert small["rotated"] is False
    assert small["reason"] == "under_limit"
