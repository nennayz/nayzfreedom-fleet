from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from models.content_job import ContentJob, CheckpointDecision

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

    if unattended:
        decision = _UNATTENDED_DECISIONS.get(stage, "approved")
        print(f"  [unattended] auto-decision: {decision}")
    else:
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  [{i}] {opt}")
        print()
        decision = input("Your choice (or type freely): ").strip()

    job.checkpoint_log.append(
        CheckpointDecision(stage=stage, decision=decision, timestamp=datetime.now())
    )
    return CheckpointResult(stage=stage, decision=decision)
