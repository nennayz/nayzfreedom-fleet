from agents.nora import NoraAgent
from tests.test_lila import make_job_with_bella_output
from tests.test_mia import make_config
from models.content_job import QAResult


def make_job_for_nora(dry_run=True):
    job = make_job_with_bella_output(dry_run=dry_run)
    job.visual_prompt = "Gold lipstick, ivory background"
    job.image_path = "assets/placeholder.png"
    return job


def test_nora_dry_run_passes():
    agent = NoraAgent(make_config())
    job = agent.run(make_job_for_nora(dry_run=True))
    assert job.qa_result is not None
    assert job.qa_result.passed is True
    assert job.stage == "nora_done"


def test_nora_live_fail_increments_retry(mocker):
    qa_json = '{"passed":false,"script_feedback":"Hook too weak","visual_feedback":null,"send_back_to":"bella"}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False)
    job = agent.run(job)
    assert job.qa_result.passed is False
    assert job.qa_result.send_back_to == "bella"
    assert job.nora_retry_count == 1


def test_nora_live_pass(mocker):
    qa_json = '{"passed":true,"script_feedback":null,"visual_feedback":null,"send_back_to":null}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = agent.run(make_job_for_nora(dry_run=False))
    assert job.qa_result.passed is True
    assert job.nora_retry_count == 0
