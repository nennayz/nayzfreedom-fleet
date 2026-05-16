from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from datetime import datetime

from models.content_job import ContentJob, CheckpointDecision

import telegram_checkpoint

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
try:
    TELEGRAM_TIMEOUT_MINUTES = int(os.environ.get("TELEGRAM_TIMEOUT_MINUTES", "30"))
except ValueError:
    logger.warning("Invalid TELEGRAM_TIMEOUT_MINUTES, defaulting to 30")
    TELEGRAM_TIMEOUT_MINUTES = 30

if bool(TELEGRAM_BOT_TOKEN) != bool(TELEGRAM_CHAT_ID):
    logger.warning(
        "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set. "
        "Telegram checkpoints disabled — falling back to input()."
    )

_UNATTENDED_DECISIONS: dict[str, str] = {
    "idea_selection": "1",
    "content_review": "approved",
    "qa_review": "approved",
    "final_approval": "approved",
}


@dataclass
class CheckpointResult:
    stage: str
    decision: str


def pause(
    stage: str,
    summary: str,
    options: list[str],
    job: ContentJob,
    unattended: bool = False,
) -> CheckpointResult:
    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {stage.upper().replace('_', ' ')}")
    print(f"{'='*60}")
    print(f"\n{summary}\n")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and not unattended:
        decision = telegram_checkpoint.send_and_wait(
            stage=stage,
            summary=summary,
            options=options,
            token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
            timeout_seconds=TELEGRAM_TIMEOUT_MINUTES * 60,
            fallback=_UNATTENDED_DECISIONS.get(stage, "approved"),
        )
    elif not unattended:
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  [{i}] {opt}")
        print()
        decision = input("Your choice (or type freely): ").strip()
    else:
        if stage == "idea_selection" and options:
            first = options[0].split(":", 1)[0].strip()
            decision = first if first.isdigit() else "1"
        else:
            decision = _UNATTENDED_DECISIONS.get(stage, "approved")
        print(f"  [unattended] auto-decision: {decision}")

    job.checkpoint_log.append(
        CheckpointDecision(stage=stage, decision=decision, timestamp=datetime.now())
    )
    return CheckpointResult(stage=stage, decision=decision)
