from agents.roxy import RoxyAgent
from tests.test_nora import make_job_for_nora
from tests.test_mia import make_config
from models.content_job import GrowthStrategy, QAResult

def make_job_post_qa(dry_run=True):
    job = make_job_for_nora(dry_run=dry_run)
    job.qa_result = QAResult(passed=True)
    return job

def test_roxy_dry_run_returns_strategy():
    agent = RoxyAgent(make_config())
    job = agent.run(make_job_post_qa(dry_run=True))
    assert isinstance(job.growth_strategy, GrowthStrategy)
    assert len(job.growth_strategy.hashtags) >= 5
    assert job.growth_strategy.caption != ""
    assert job.stage == "roxy_done"

def test_roxy_live_calls_claude(mocker):
    strategy_json = ('{"hashtags":["#LipHack","#GlossyLips"],'
                     '"caption":"your new fave hack","best_post_time_utc":"13:00","best_post_time_thai":"20:00"}')
    mocker.patch.object(RoxyAgent, "_call_claude", return_value=strategy_json)
    agent = RoxyAgent(make_config())
    job = agent.run(make_job_post_qa(dry_run=False))
    assert job.growth_strategy.hashtags == ["#LipHack", "#GlossyLips"]
    assert job.growth_strategy.editorial_guidance == {}

def test_roxy_dry_run_strategy_has_editorial_guidance():
    agent = RoxyAgent(make_config())
    job = agent.run(make_job_post_qa(dry_run=True))
    assert isinstance(job.growth_strategy.editorial_guidance, dict)
    assert len(job.growth_strategy.editorial_guidance) > 0
    assert "instagram" in job.growth_strategy.editorial_guidance
