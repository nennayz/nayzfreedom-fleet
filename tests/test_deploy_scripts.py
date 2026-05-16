from __future__ import annotations
import subprocess
from pathlib import Path


def test_backup_and_healthcheck_scripts_parse():
    for path in ("deploy/backup.sh", "deploy/healthcheck.sh"):
        result = subprocess.run(["bash", "-n", path], cwd=Path(__file__).resolve().parents[1])
        assert result.returncode == 0


def test_instagram_queue_systemd_units_exist():
    root = Path(__file__).resolve().parents[1]
    service = root / "deploy" / "nayzfreedom-instagram-queue.service"
    timer = root / "deploy" / "nayzfreedom-instagram-queue.timer"
    assert service.exists()
    assert timer.exists()
    assert "instagram_queue.py" in service.read_text()
    assert "OnUnitActiveSec=5min" in timer.read_text()
