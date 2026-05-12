from agents.lila import LilaAgent
from tests.test_bella import make_job_with_idea
from tests.test_mia import make_config
from models.content_job import Script

def make_job_with_script(dry_run=True):
    job = make_job_with_idea(dry_run=dry_run)
    job.script = Script(hook="h", body="b", cta="c", duration_seconds=30)
    return job

def test_lila_dry_run_sets_visual_prompt_and_image():
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_script(dry_run=True))
    assert job.visual_prompt is not None
    assert job.image_path is not None
    assert job.stage == "lila_done"

def test_lila_live_calls_claude_for_prompt(mocker):
    prompt = "Cinematic shot of gold lipstick, ivory background, soft morning light"
    mocker.patch.object(LilaAgent, "_call_claude", return_value=prompt)
    mocker.patch.object(LilaAgent, "_generate_image", return_value="output/test/image.png")
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_script(dry_run=False))
    assert job.visual_prompt == prompt
    assert job.image_path == "output/test/image.png"
