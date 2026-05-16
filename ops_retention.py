from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


def _rotate_jsonl_log(root: Path, filename: str, archive_prefix: str, max_bytes: int, keep_lines: int) -> dict[str, object]:
    log_path = root / "logs" / filename
    if not log_path.exists():
        return {"rotated": False, "reason": "missing", "path": str(log_path)}

    size = log_path.stat().st_size
    if size <= max_bytes:
        return {"rotated": False, "reason": "under_limit", "size_bytes": size}

    lines = log_path.read_text().splitlines()
    archive_dir = root / "logs" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"{archive_prefix}-{stamp}.jsonl"
    archive_path.write_text("\n".join(lines) + "\n")

    kept = lines[-keep_lines:] if keep_lines > 0 else []
    log_path.write_text(("\n".join(kept) + "\n") if kept else "")
    return {
        "rotated": True,
        "size_bytes": size,
        "archive": str(archive_path),
        "kept_lines": len(kept),
    }


def rotate_ops_log(root: Path, max_bytes: int = 1_000_000, keep_lines: int = 500) -> dict[str, object]:
    return _rotate_jsonl_log(root, "ops_actions.jsonl", "ops_actions", max_bytes, keep_lines)


def rotate_work_activity_log(root: Path, max_bytes: int = 1_000_000, keep_lines: int = 500) -> dict[str, object]:
    return _rotate_jsonl_log(root, "work_activity.jsonl", "work_activity", max_bytes, keep_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate Slayhack Ops audit logs.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--keep-lines", type=int, default=500)
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
    ops_result = rotate_ops_log(root, max_bytes=args.max_bytes, keep_lines=args.keep_lines)
    work_result = rotate_work_activity_log(root, max_bytes=args.max_bytes, keep_lines=args.keep_lines)
    print("ops " + " ".join(f"{key}={value}" for key, value in ops_result.items()))
    print("work_activity " + " ".join(f"{key}={value}" for key, value in work_result.items()))


if __name__ == "__main__":
    main()
