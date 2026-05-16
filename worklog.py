from __future__ import annotations

import argparse
from pathlib import Path

from work_activity import VALID_EVENT_TYPES, write_work_activity

ALIASES = {
    "command": "terminal_command",
    "decision": "design_decision",
    "implement": "implementation_step",
    "test": "test_result",
    "deploy": "deploy_step",
    "smoke": "production_smoke",
    "recommend": "next_recommendation",
}


def _event_type(value: str) -> str:
    normalized = value.replace("-", "_")
    normalized = ALIASES.get(normalized, normalized)
    if normalized not in VALID_EVENT_TYPES:
        choices = ", ".join(sorted(VALID_EVENT_TYPES | set(ALIASES)))
        raise argparse.ArgumentTypeError(f"invalid event type {value!r}; choose one of: {choices}")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a Slayhack work activity entry.")
    parser.add_argument("event_type", type=_event_type)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--actor", default="codex")
    parser.add_argument("--command", default=None)
    parser.add_argument("--file", action="append", dest="files", default=[])
    parser.add_argument("--result", default=None)
    parser.add_argument("--next-action", default=None)
    parser.add_argument("--root", default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
    record = write_work_activity(
        root,
        args.event_type,
        args.summary,
        actor=args.actor,
        command=args.command,
        files=args.files,
        result=args.result,
        next_action=args.next_action,
    )
    print(f"work_activity={record['event_type']} timestamp={record['timestamp']}")


if __name__ == "__main__":
    main()
