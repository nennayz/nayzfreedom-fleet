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
