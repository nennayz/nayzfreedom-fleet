import base64
import openai
from pathlib import Path
import pytest
from agents.lila import LilaAgent
from tests.test_bella import make_job_with_idea
from tests.test_mia import make_config
from models.content_job import Script, ContentType, Article, ImageCaption, InfographicContent


def make_job_with_bella_output(dry_run=True):
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.VIDEO)
    job.bella_output = Script(hook="h", body="b", cta="c", duration_seconds=30)
    return job


def test_lila_dry_run_sets_visual_prompt_and_image():
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=True))
    assert job.visual_prompt is not None
    assert job.image_path is not None
    assert job.stage == "lila_done"


def test_lila_live_calls_claude_for_prompt(mocker):
    prompt = "Cinematic shot of gold lipstick, ivory background, soft morning light"
    mocker.patch.object(LilaAgent, "_call_claude", return_value=prompt)
    mocker.patch.object(LilaAgent, "_generate_image", return_value="output/test/image.png")
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=False))
    assert job.visual_prompt == prompt
    # VIDEO jobs produce a prompt but no image in Phase 1
    assert job.image_path is None


def make_article_job(dry_run=True):
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.ARTICLE)
    job.bella_output = Article(heading="The Look", body="Step 1...", cta="Shop now")
    return job


def make_image_job(dry_run=True):
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.IMAGE)
    job.bella_output = ImageCaption(caption="Soft glam", alt_text="Woman in gold tones")
    return job


def test_lila_skips_for_article():
    agent = LilaAgent(make_config())
    job = agent.run(make_article_job(dry_run=True))
    assert job.visual_prompt is None
    assert job.image_path is None
    assert job.stage == "lila_done"


def test_lila_dry_run_image_generates_prompt():
    agent = LilaAgent(make_config())
    job = agent.run(make_image_job(dry_run=True))
    assert job.visual_prompt is not None
    assert job.image_path is not None
    assert job.stage == "lila_done"


def test_lila_live_article_skips_claude(mocker):
    mock_call = mocker.patch.object(LilaAgent, "_call_claude")
    agent = LilaAgent(make_config())
    agent.run(make_article_job(dry_run=False))
    mock_call.assert_not_called()


def test_lila_live_image_calls_openai(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_b64 = base64.b64encode(b"PNG_BYTES").decode()
    mock_response = mocker.MagicMock()
    mock_response.data = [mocker.MagicMock(b64_json=fake_b64)]
    mock_client = mocker.MagicMock()
    mock_client.images.generate.return_value = mock_response
    mocker.patch("agents.lila.openai.OpenAI", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="gold lipstick on marble")
    agent = LilaAgent(make_config())
    job = make_image_job(dry_run=False)
    job = agent.run(job)
    mock_client.images.generate.assert_called_once_with(
        model="gpt-image-1",
        prompt="gold lipstick on marble",
        n=1,
        size="1024x1024",
        response_format="b64_json",
    )
    assert job.image_path is not None
    assert job.image_path.endswith("image.png")
    assert Path(job.image_path).read_bytes() == b"PNG_BYTES"
    assert job.stage == "lila_done"


def test_lila_live_infographic_calls_openai(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_b64 = base64.b64encode(b"PNG_BYTES").decode()
    mock_response = mocker.MagicMock()
    mock_response.data = [mocker.MagicMock(b64_json=fake_b64)]
    mock_client = mocker.MagicMock()
    mock_client.images.generate.return_value = mock_response
    mocker.patch("agents.lila.openai.OpenAI", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="clean white infographic layout")
    agent = LilaAgent(make_config())
    job = make_job_with_idea(dry_run=False, content_type=ContentType.INFOGRAPHIC)
    job.bella_output = InfographicContent(title="T", points=["p1"], cta="c")
    job = agent.run(job)
    mock_client.images.generate.assert_called_once_with(
        model="gpt-image-1",
        prompt="clean white infographic layout",
        n=1,
        size="1024x1024",
        response_format="b64_json",
    )
    assert job.image_path is not None
    assert job.image_path.endswith("image.png")
    assert job.stage == "lila_done"


def test_lila_live_image_openai_error_raises_runtime(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_client = mocker.MagicMock()
    mock_client.images.generate.side_effect = openai.OpenAIError("quota exceeded")
    mocker.patch("agents.lila.openai.OpenAI", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="some prompt")
    agent = LilaAgent(make_config())
    job = make_image_job(dry_run=False)
    with pytest.raises(RuntimeError, match=job.id):
        agent.run(job)
