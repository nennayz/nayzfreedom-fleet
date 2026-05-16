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


def test_lila_dry_run_video_sets_video_path():
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=True))
    assert job.visual_prompt is not None
    assert job.video_path is not None
    assert job.image_path is None
    assert job.stage == "lila_done"


def test_lila_live_video_calls_claude_and_generate_video(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prompt = "Cinematic shot of gold lipstick, ivory background, soft morning light"
    mocker.patch.object(LilaAgent, "_call_claude", return_value=prompt)
    mocker.patch.object(LilaAgent, "_generate_video", return_value=str(tmp_path / "video.mp4"))
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=False))
    assert job.visual_prompt == prompt
    assert job.video_path == str(tmp_path / "video.mp4")
    assert job.image_path is None
    assert job.stage == "lila_done"


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
        model="gpt-image-2",
        prompt="gold lipstick on marble",
        n=1,
        size="1024x1024",
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
        model="gpt-image-2",
        prompt="clean white infographic layout",
        n=1,
        size="1024x1024",
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


def _make_genai_client_mock(mocker, video_bytes=b"VIDEO_BYTES", done_sequence=None):
    mock_operation = mocker.MagicMock()
    if done_sequence is not None:
        type(mock_operation).done = mocker.PropertyMock(side_effect=done_sequence)
    else:
        type(mock_operation).done = mocker.PropertyMock(return_value=True)
    mock_operation.result.generated_videos = [
        mocker.MagicMock(video=mocker.MagicMock(video_bytes=video_bytes))
    ]
    mock_client = mocker.MagicMock()
    mock_client.models.generate_videos.return_value = mock_operation
    mock_client.operations.get.return_value = mock_operation
    mocker.patch("agents.lila.genai.Client", return_value=mock_client)
    return mock_client, mock_operation


def test_lila_live_video_calls_veo3(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_client, _ = _make_genai_client_mock(mocker)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="cinematic video prompt")
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=False))
    mock_client.models.generate_videos.assert_called_once_with(
        model="veo-2.0-generate-001",
        prompt="cinematic video prompt",
    )
    assert job.video_path is not None
    assert job.video_path.endswith("video.mp4")
    assert Path(job.video_path).read_bytes() == b"VIDEO_BYTES"
    assert job.image_path is None
    assert job.stage == "lila_done"


def test_lila_live_video_timeout_raises_runtime(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_client, mock_operation = _make_genai_client_mock(mocker, done_sequence=[False, False])
    mocker.patch("agents.lila.time.sleep")
    mocker.patch("agents.lila.time.time", side_effect=[0, 601])
    mocker.patch.object(LilaAgent, "_call_claude", return_value="some prompt")
    agent = LilaAgent(make_config())
    job = make_job_with_bella_output(dry_run=False)
    with pytest.raises(RuntimeError, match=job.id):
        agent.run(job)


def test_lila_live_video_google_error_raises_runtime(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_client = mocker.MagicMock()
    mock_client.models.generate_videos.side_effect = Exception("API quota exceeded")
    mocker.patch("agents.lila.genai.Client", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="some prompt")
    agent = LilaAgent(make_config())
    job = make_job_with_bella_output(dry_run=False)
    with pytest.raises(RuntimeError, match=job.id):
        agent.run(job)


def test_lila_live_video_generate_video_prompt_guard(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mocker.patch("agents.lila.genai.Client")
    agent = LilaAgent(make_config())
    job = make_job_with_bella_output(dry_run=False)
    job.visual_prompt = None
    with pytest.raises(ValueError, match=job.id):
        agent._generate_video(job)
