from unittest.mock import patch
from checkpoint import pause, CheckpointResult
from models.content_job import ContentJob, PMProfile, BrandProfile, VisualIdentity


def make_job():
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""), platforms=[],
        tone="", target_audience="", script_style="", nora_max_retries=2,
    )
    pm = PMProfile(name="Test", page_name="Test Page", persona="", brand=brand)
    return ContentJob(project="test", pm=pm, brief="b", platforms=[])


def test_pause_approve(capsys):
    with patch("builtins.input", return_value="y"):
        result = pause("qa_review", "Script looks good.", [], make_job())
    assert result.decision == "y"
    assert result.stage == "qa_review"


def test_pause_records_to_checkpoint_log():
    job = make_job()
    with patch("builtins.input", return_value="skip"):
        result = pause("ideation", "Pick an idea.", ["1", "2", "3"], job)
    assert len(job.checkpoint_log) == 1
    assert job.checkpoint_log[0].stage == "ideation"
    assert job.checkpoint_log[0].decision == "skip"


def test_pause_unattended_idea_selection_returns_1():
    job = make_job()
    result = pause("idea_selection", "Pick an idea.", ["Idea A", "Idea B"], job, unattended=True)
    assert result.decision == "1"
    assert result.stage == "idea_selection"
    assert len(job.checkpoint_log) == 1
    assert job.checkpoint_log[0].decision == "1"


def test_pause_unattended_other_stages_returns_approved():
    job = make_job()
    for stage in ("content_review", "qa_review", "final_approval"):
        job.checkpoint_log.clear()
        result = pause(stage, "summary", [], job, unattended=True)
        assert result.decision == "approved"
        assert result.stage == stage


def test_pause_unattended_unknown_stage_returns_approved():
    job = make_job()
    result = pause("some_future_stage", "summary", [], job, unattended=True)
    assert result.decision == "approved"


def test_pause_unattended_does_not_call_input(monkeypatch):
    called = []
    monkeypatch.setattr("builtins.input", lambda _: called.append(1) or "x")
    job = make_job()
    pause("qa_review", "summary", [], job, unattended=True)
    assert called == []
