import sys
import main as main_module
from unittest.mock import patch
from checkpoint import pause, CheckpointResult
from models.content_job import ContentJob, PMProfile, BrandProfile, VisualIdentity, ContentType


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


def test_main_content_type_flag_sets_job_content_type(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    returned_job = make_job()
    returned_job.status = __import__('models.content_job', fromlist=['JobStatus']).JobStatus.COMPLETED
    mock_orch = mocker.patch.object(main_module.Orchestrator, "run", return_value=returned_job)
    mocker.patch.object(main_module.Config, "from_env", return_value=mocker.MagicMock())
    mocker.patch("main.load_project", return_value=make_job().pm)
    sys.argv = ["main.py", "--project", "slay_hack", "--brief", "test brief", "--content-type", "article"]
    try:
        main_module.main()
    except SystemExit:
        pass
    assert mock_orch.called
    job_arg = mock_orch.call_args[0][0]
    assert job_arg.content_type == ContentType.ARTICLE


def test_main_unattended_flag_passed_to_orchestrator(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    returned_job = make_job()
    returned_job.status = __import__('models.content_job', fromlist=['JobStatus']).JobStatus.COMPLETED
    mock_run = mocker.patch.object(main_module.Orchestrator, "run", return_value=returned_job)
    mocker.patch.object(main_module.Config, "from_env", return_value=mocker.MagicMock())
    mocker.patch("main.load_project", return_value=make_job().pm)
    sys.argv = ["main.py", "--project", "slay_hack", "--brief", "test brief", "--unattended"]
    try:
        main_module.main()
    except SystemExit:
        pass
    assert mock_run.called
    _, kwargs = mock_run.call_args
    assert kwargs.get("unattended") is True
