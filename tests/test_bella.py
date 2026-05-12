from agents.bella import BellaAgent
from tests.test_mia import make_config, make_job
from models.content_job import Idea, Script


def make_job_with_idea(dry_run=True):
    job = make_job(dry_run=dry_run)
    job.selected_idea = Idea(number=1, title="Lip Hack", hook="pov your lips last all day", angle="Tutorial")
    return job


def test_bella_dry_run_returns_script():
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=True))
    assert isinstance(job.script, Script)
    assert job.script.hook != ""
    assert job.script.cta != ""
    assert job.stage == "bella_done"


def test_bella_live_calls_claude(mocker):
    script_json = '{"hook":"wait—","body":"step 1: do this","cta":"save this","duration_seconds":30}'
    mocker.patch.object(BellaAgent, "_call_claude", return_value=script_json)
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=False))
    assert job.script.hook == "wait—"
    assert job.script.duration_seconds == 30
